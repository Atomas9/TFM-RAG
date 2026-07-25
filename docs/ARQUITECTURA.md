# Arquitectura del sistema

## Objetivo

Construir un RAG trazable sobre partes diarios de MITECO que permita recuperar
informacion por similitud semantica, por metadatos o combinando ambos metodos.

## Flujo de ingesta

```text
MITECO
  -> GitHub Actions, dos intentos diarios
  -> descubrimiento y validacion del parte definitivo
  -> fecha interna, hash SHA-256 y manifiesto JSONL
  -> almacenamiento versionado en data/raw/miteco
  -> extraccion por paginas con PyMuPDF
  -> parser especifico basado en una maquina de estados
  -> validacion de FireSnapshot con Pydantic
  -> validacion agregada y ParserReport
  -> exportacion JSONL y JSON en data/processed
  -> embeddings BAAI/bge-m3
  -> ChromaDB en data/chroma
```

## Flujo de consulta

```text
pregunta
  -> normalizacion y deteccion de filtros
  -> consulta semantica, estructurada o combinada en ChromaDB
  -> seleccion de top-k snapshots
  -> construccion de contexto con fuentes
  -> respuesta con Ollama Cloud
```

## Componentes

| Responsabilidad | Tecnologia |
| --- | --- |
| Descarga programada | GitHub Actions, httpx y Beautiful Soup |
| Lectura de PDF | PyMuPDF |
| Esquemas y validacion | Pydantic |
| Normalizacion aproximada | unicodedata y RapidFuzz |
| Embeddings | Sentence Transformers y BAAI/bge-m3 |
| Base vectorial | ChromaDB |
| Generacion | Ollama y gemma4:31b-cloud |
| Pruebas | pytest |

La ingesta automática es una etapa independiente. Dos ejecuciones diarias
descargan el enlace estable de MITECO, pero la fecha se obtiene del contenido
del PDF. Solo se acepta el parte del día anterior en `Europe/Madrid`. El hash
evita duplicados y `manifest.jsonl` conserva procedencia y revisiones. En esta
fase el workflow no relanza el parser ni actualiza Chroma.

## Unidad documental

La unidad principal sera un snapshot: el estado de un incendio en una fecha de
parte determinada. Un mismo incendio puede generar varios snapshots a lo largo
de varios dias y no deben eliminarse como duplicados.

Se distinguen dos niveles de identidad:

- `snapshot_id` es unico para cada bloque dentro de un PDF y se deriva del hash
  del documento, el ordinal y la localizacion normalizada;
- `incident_key` es una agrupacion heuristica basada en pais, comunidad,
  provincia, localizacion y fecha de inicio cuando esta disponible.

Cuando falta la fecha de inicio, dos partes de la misma ubicacion comparten
`incident_key`. Esto permite recuperar una posible serie temporal, pero tambien
puede unir incendios diferentes ocurridos en el mismo lugar. En sentido
contrario, si la fecha aparece en un parte y falta en otro, un mismo incendio
puede quedar dividido. La identidad definitiva requerira una fase posterior de
resolucion temporal que considere continuidad entre partes, estado y fechas
explicitas. Por tanto, `incident_key` no se usara para eliminar snapshots.

El parser mantendra como estado, al menos:

- comunidad autonoma actual;
- provincia actual;
- numero de pagina;
- incendio actualmente abierto.

La orquestacion se divide en dos niveles:

- `parse_miteco_pdf(pdf_path, source_url=None)` ejecuta extraccion, metadatos,
  separacion de bloques y construccion de snapshots para un unico documento;
- `parse_pdf_directory(input_dir)` ordena los PDF por ruta, procesa cada uno y
  concatena sus snapshots sin deduplicarlos.

El orden determinista permite repetir una ejecucion y comparar su salida. La
deduplicacion por `incident_key` queda expresamente fuera de esta etapa porque
un mismo incendio puede tener un snapshot diferente cada dia.

`validate_snapshots()` comprueba identificadores duplicados, rangos de paginas,
contaminacion con el resumen estadistico y ausencias relevantes. Los errores
bloquean la exportacion; las advertencias se conservan en el informe.

`run_phase1()` genera:

- `fire_snapshots.jsonl`: un objeto `FireSnapshot` por linea;
- `parser_report.json`: version del parser, instante UTC, documentos, recuentos,
  advertencias y errores de la ejecucion.

La salida se reconstruye desde todos los PDF en cada ejecucion. Este enfoque es
deliberado mientras el corpus sea pequeno y el esquema siga evolucionando. Una
futura ingesta incremental comparara `source_sha256` y `parser_version` antes de
decidir que documentos deben reprocesarse.

## Indexacion vectorial implementada

`src/miteco_rag/embeddings_chroma.py` realiza el primer indice denso del
proyecto:

1. lee `data/processed/fire_snapshots.jsonl` linea a linea;
2. reconstruye y valida cada linea como `FireSnapshot` con Pydantic;
3. usa `chunk_text` como unidad de embedding y como documento recuperable;
4. genera los vectores con `BAAI/bge-m3`, CPU, lotes de ocho y normalizacion;
5. convierte los metadatos a tipos planos admitidos por Chroma y omite los
   valores `None`;
6. abre una base persistente en `data/chroma`;
7. inserta o actualiza la coleccion `MITECO_fire_snapshots` mediante
   `snapshot_id`.

El indice actual incluye los 48 snapshots del JSONL: 47 de Espana y uno de
Portugal. Esta inclusion es deliberada; `country` permite aplicar un filtro
posterior cuando una consulta deba limitarse a Espana.

Chroma se configura con `embedding_function=None` porque los vectores se
calculan fuera de la base de datos. Las consultas semanticas deberan usar el
mismo modelo y la misma normalizacion. Los vectores comprobados tienen 1.024
dimensiones y norma unitaria.

La escritura actual usa `get_or_create_collection()` y `upsert()`. Esto hace
repetible la indexacion de los mismos snapshots, pero no constituye una
sincronizacion completa: si un ID desaparece del JSONL, su registro anterior no
se borra de Chroma. Antes de automatizar la ingesta habra que elegir entre
recrear la coleccion o eliminar expresamente los IDs obsoletos.

## Metadatos minimos

- `snapshot_id`
- `incident_key`
- `document_id`
- `country`
- `autonomous_community`
- `autonomous_community_normalized`
- `province`
- `province_normalized`
- `location`
- `location_normalized`
- `status`
- `operational_status`
- `report_date`
- `report_date_number`
- `last_update`
- `page_start`
- `page_end`
- `source_file`
- `source_url`
- `source_sha256`
- `parser_version`
- `raw_text`
- `chunk_text`

## Modos de recuperacion

1. Metadatos: `collection.get(where=...)`.
2. Semantica: `collection.query(query_embeddings=...)`.
3. Combinada: embedding de la pregunta junto con `where`.

Las ubicaciones se normalizan antes de almacenarlas y consultarlas. Las
variantes o errores tipograficos deben resolverse en la aplicacion antes de
enviar un filtro exacto a Chroma.

## Retrieval implementado

La consulta se divide en dos modulos:

- `query_filters.py` interpreta la pregunta sin abrir Chroma ni cargar el
  modelo;
- `retrieval_chroma.py` conserva la implementacion en desarrollo del alumno;
- `extras/retrieval_chroma_solution.py` conserva como referencia cómo generar
  el embedding y ejecutar `collection.query()` con el `where` construido.

El analizador produce primero un `ParsedQuery` que conserva:

- pregunta original y consulta semantica;
- valores incluidos y excluidos por campo;
- intervalo de fechas del parte;
- contradicciones o ambiguedades detectadas.

`MetadataCatalog` conserva ademas las fechas de parte disponibles, los anos y
`latest_report_date`. No se duplican mes y ano en Chroma: las consultas por
mes o ano se traducen a limites sobre `report_date_number`.

`build_chroma_where()` realiza despues una traduccion independiente a `$and`,
`$in`, `$nin`, `$ne`, `$gte` y `$lte`. Esta separacion permite probar si un
error procede de la interpretacion linguistica o de la condicion enviada a la
base de datos.

Para el uso habitual, `metadata_query(question, catalog)` encapsula ambos
pasos, bloquea las ambiguedades y devuelve directamente el diccionario `where`
o `None` cuando no reconoce filtros.

Los campos soportados son:

- `country`;
- `autonomous_community_normalized`;
- `province_normalized`;
- `location_normalized`;
- `status`;
- `operational_status`;
- `report_date_number`.

Los catalogos completos de comunidades y provincias permiten reconocer una
provincia aunque no tenga incendios en el corpus actual. En ese caso Chroma
devuelve cero registros. Las localizaciones son dinamicas y se construyen con
los metadatos existentes, porque cada parte puede introducir nombres nuevos.

El orden de prioridad evita interpretar `Leon` dentro de `Castilla y Leon` y
resuelve expresiones como `no de Leon sino de Palencia`. Las contradicciones no
se ejecutan: se devuelve un error explicito para solicitar una aclaracion.

La interpretacion temporal distingue tres casos:

- una fecha, mes o ano explicito se convierte en fecha exacta o intervalo;
- `activo` y expresiones presentes como `hay`, `existen`, `actualmente`,
  `ahora`, `a dia de hoy` o `ultimo parte` usan el ultimo parte disponible;
- formas historicas como `estuvieron activos` no reciben automaticamente la
  fecha maxima.

El ultimo parte es la fecha maxima del corpus, no informacion en tiempo real.
Las respuestas posteriores deberan comunicar siempre la fecha de referencia.

La funcion de bajo nivel `retrieve()` admite un `where` manual. La funcion
`retrieve_with_filters()` construye el catalogo, interpreta la pregunta,
comprueba ambiguedades y devuelve resultados, interpretacion y filtro final.

Todavia no existe un planificador que elija entre `get()` y `query()`: la ruta
automatica actual siempre hace ranking vectorial dentro de los registros que
cumplen el filtro. Tampoco se ha incorporado busqueda lexica.

El primer generador aumentado ya formatea los chunks y responde con Ollama
Cloud. Aun no existe un evaluador de suficiencia posterior al retrieval ni un
planificador de recuperación.

El revisor LLM de filtros ya existe como función independiente. Devuelve un
`FilterReview` estructurado que separa coherencia y suficiencia y decide entre
`keep`, `extend`, `replace` y `clarify`. Todavía faltan sus pruebas
automatizadas con dobles, el generador de intención para corregir filtros y el
clasificador de dominio.

La siguiente iteracion completara estos componentes antes de orquestarlos con
LangGraph. El generador LLM devolverá condiciones y grupos lógicos validados,
no un `where` libre.

Un nodo determinista reconciliara ambas interpretaciones campo por campo,
conservara la procedencia de cada filtro y construira el `where`. Otro nodo
elegira entre ranking semantico, retrieval hibrido, recuperación exhaustiva,
recuento o linea temporal.

Tras consultar Chroma se distinguira entre contexto suficiente, cero
coincidencias exactas, mala similitud y cobertura incompleta. Solo los dos
ultimos casos podran activar un segundo y ultimo retrieval.

El diseño completo, los grafos de ramas, el estado y los nodos previstos se
describen en [ARQUITECTURA_LANGGRAPH.md](ARQUITECTURA_LANGGRAPH.md).

## Limites iniciales

- Corpus centrado en Espana y en documentos de MITECO.
- Ejecucion local del parser, embeddings e indice.
- Generacion remota opcional mediante Ollama Cloud.
- Sin LangChain ni LlamaIndex durante la primera implementacion.
