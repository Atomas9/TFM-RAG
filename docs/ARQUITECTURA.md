# Arquitectura del sistema

## Objetivo

Construir un RAG trazable sobre partes diarios de MITECO que permita recuperar
informacion por similitud semantica, por metadatos o combinando ambos metodos.

## Flujo de ingesta

```text
MITECO
  -> descarga del PDF y hash SHA-256
  -> almacenamiento en data/raw/miteco
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
| Descarga | httpx y Beautiful Soup |
| Lectura de PDF | PyMuPDF |
| Esquemas y validacion | Pydantic |
| Normalizacion aproximada | unicodedata y RapidFuzz |
| Embeddings | Sentence Transformers y BAAI/bge-m3 |
| Base vectorial | ChromaDB |
| Generacion | Ollama y gemma4:31b-cloud |
| Pruebas | pytest |

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

Las ubicaciones se normalizaran antes de almacenarlas y consultarlas. Las
variantes o errores tipograficos se resolveran en la aplicacion antes de enviar
un filtro exacto a Chroma.

Estos tres modos pertenecen al siguiente incremento. La fase implementada
termina en la persistencia del indice; todavia no hay un componente de consulta
ni una llamada al LLM.

## Limites iniciales

- Corpus centrado en Espana y en documentos de MITECO.
- Ejecucion local del parser, embeddings e indice.
- Generacion remota opcional mediante Ollama Cloud.
- Sin LangChain ni LlamaIndex durante la primera implementacion.
