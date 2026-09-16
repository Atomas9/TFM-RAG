# Arquitectura del RAG de incendios de MITECO

## 1. Objetivo y alcance

El sistema permite consultar en lenguaje natural los partes diarios de intervenciones en incendios forestales publicados por MITECO. Combina recuperación semántica, filtros estructurados y operaciones exactas sobre metadatos.

El corpus representa actuaciones recogidas por MITECO, no todos los incendios ocurridos en España. Las respuestas deben interpretarse siempre dentro de los documentos disponibles.

## 2. Vista general

```text
MITECO
  -> descarga y validación
  -> PDF versionados
  -> parser
  -> FireSnapshot JSONL (fuente procesada)
       ├─> Sentence Transformers -> ChromaDB
       └─> metadatos ------------> SQLite

Pregunta y conversación
  -> preparación y reescritura contextual
  -> control temático
  -> filtros deterministas
  -> revisión/corrección opcional con LLM
  -> selección de recuperación
       ├─> híbrida: ChromaDB
       ├─> mínimo/máximo: SQLite + ChromaDB
       └─> recuento: SQLite
  -> contexto
  -> respuesta con Ollama Cloud
```

## 3. Ingesta documental

### 3.1 Descarga

`download_miteco_report.py` localiza el parte definitivo, valida que el archivo sea un PDF coherente con la fecha solicitada, calcula su SHA-256 y actualiza el manifiesto. El workflow de GitHub Actions ejecuta este proceso dos veces al día y solo crea un commit cuando existe un documento nuevo o una revisión real.

Los PDF y el manifiesto se versionan en `data/raw/miteco/`. El resto de artefactos se regenera localmente y no se almacena en Git.

### 3.2 Parseo y chunking

`parseo_y_chuncking.py` utiliza PyMuPDF para leer el texto manteniendo página y orden. Después:

1. limpia y normaliza las líneas;
2. conserva el contexto geográfico del documento;
3. identifica bloques iniciados por `Localización:`;
4. extrae país, comunidad, provincia, localidad, estado, situación operativa, medios, notas y fechas;
5. construye y valida un `FireSnapshot` con Pydantic;
6. genera un `chunk_text` autosuficiente para recuperación y respuesta.

Cada snapshot corresponde a un incendio en una fecha de parte. `snapshot_id` identifica esa observación concreta. `incident_key` intenta agrupar observaciones del mismo incendio mediante geografía, localización y fecha de inicio; es una heurística, no una identidad oficial.

El parser genera:

- `data/processed/fire_snapshots.jsonl`: un snapshot por línea;
- `data/processed/parser_report.json`: archivos procesados, recuentos, advertencias y errores.

Actualmente vuelve a procesar todos los PDF. La indexación incremental del parser es una mejora futura.

## 4. Persistencia e indexación

### 4.1 ChromaDB

`embeddings_chroma.py` transforma cada `chunk_text` con `BAAI/bge-m3`, normaliza el embedding y almacena en ChromaDB:

- `snapshot_id` como identificador;
- el texto enriquecido como documento;
- el vector semántico;
- los metadatos usados por los filtros;
- una firma de indexación.

La firma combina el contenido relevante y la configuración del modelo. De este modo, el script solo carga BGE-M3 y recalcula los registros nuevos o modificados. La escritura utiliza `upsert`. Los identificadores obsoletos se detectan, pero todavía no se eliminan automáticamente.

### 4.2 SQLite de metadatos

`metadata_store.py` mantiene una fila por snapshot con los campos necesarios para filtrar, agregar y enlazar el resultado con Chroma mediante `snapshot_id`:

```text
snapshot_id, incident_key, report_date_number, country,
autonomous_community_normalized, province_normalized,
location_normalized, status, operational_status,
source_file, source_sha256
```

SQLite evita cargar embeddings o recorrer todos los documentos para operaciones exactas como `MIN`, `MAX`, `COUNT` y, en el futuro, cronologías. El JSONL sigue siendo la fuente de verdad; esta base es un índice regenerable.

En la validación del 16 de septiembre de 2026, el JSONL, ChromaDB y SQLite contenían 324 snapshots.

## 5. Interpretación de la consulta

### 5.1 Conversación

`prepare_turn.py` valida el historial del turno. `rewrite_query.py` utiliza la conversación para convertir preguntas dependientes —por ejemplo, «¿y cuáles estaban activos?»— en una consulta autónoma. Los mensajes se acumulan en `GraphState` y LangGraph los conserva mediante `SqliteSaver` y un `thread_id`.

### 5.2 Control temático

`bouncer.py` decide si la pregunta pertenece al dominio de incendios. Una consulta ajena termina el flujo sin recuperar documentos. Las preguntas de seguimiento se evalúan después de la reescritura contextual.

### 5.3 Filtros

`query_filters.py` reconoce de forma determinista país, comunidad autónoma, provincia, localización, estado, situación operativa y fechas. También representa inclusiones, exclusiones y uniones o intersecciones en el formato `where` de ChromaDB.

El resultado determinista contiene tanto los filtros interpretados como posibles ambigüedades y el `deterministic_where`. `revisor_query_filters.py` pide a un LLM una de cuatro decisiones:

- `keep`: el filtro ya es coherente y suficiente;
- `extend`: debe completarse;
- `replace`: debe sustituirse;
- `clarify`: hace falta preguntar al usuario.

En los casos `extend` y `replace`, `generate_filter_LLM.py` devuelve una propuesta estructurada, la valida contra el catálogo permitido y construye el `final_where`. Los modelos Pydantic se serializan como diccionarios antes de guardarlos en el estado del grafo para facilitar la persistencia de checkpoints.

## 6. Estrategias de recuperación

`retrieval_mode.py` elige el modo de forma determinista.

### 6.1 Recuperación híbrida

Para preguntas descriptivas se aplica primero `final_where` y ChromaDB devuelve hasta diez documentos que cumplen el filtro, ordenados por proximidad del embedding de la pregunta. La salida común es un `RetrievalResult` plano con identificadores, documentos, metadatos, distancias y, si procede, un agregado.

### 6.2 Mínimo o máximo

Para preguntas como «¿cuál es el último parte de León?»:

1. `metadata_queries.py` traduce a SQL el mismo filtro de Chroma;
2. SQLite calcula la fecha mínima o máxima dentro del conjunto ya filtrado;
3. obtiene todos los `snapshot_id` de esa fecha;
4. ChromaDB recupera sus documentos por identificador.

Así se evita el error de calcular primero la fecha global y comprobar después si contiene resultados de León.

### 6.3 Recuentos

SQLite calcula recuentos exactos de:

- incendios únicos, mediante `incident_key`;
- snapshots;
- partes o informes distintos.

Esta ruta no carga el modelo de embeddings ni documentos completos. Un recuento de cero sigue siendo un resultado válido, no un fallo de recuperación.

### 6.4 Cronologías

El clasificador reconoce preguntas de evolución temporal, pero la rama `timeline` todavía no está conectada en el grafo. Debe considerarse trabajo pendiente.

## 7. Orquestación con LangGraph

El flujo operativo de `rag_graph.py` es:

```text
START
  -> PrepareTurn
  -> RewriteQuery
  -> Bouncer
       ├─ NO GO -> END
       └─ GO -> DeterministicAnalysis
                  -> Reviewer
                       ├─ clarify -> END
                       ├─ keep -> RetrievalMode
                       └─ extend/replace
                            -> GenerateFilter
                            -> ResolveWhere
                            -> RetrievalMode
                                 ├─ hybrid -> Retrieve
                                 ├─ min_max -> MinMaxRetrieve
                                 └─ count -> CountRetrieve
                                      -> GenerateContext
                                      -> GenerateAnswer
                                      -> END
```

Los recursos costosos se cargan una vez en `main_langgraph.py` y se inyectan en los nodos con `functools.partial`: modelo de embeddings, colección Chroma, catálogo de metadatos y conexión SQLite. El cliente de Chroma y la conexión SQLite se cierran al finalizar.

`GraphState` conserva consulta original, consulta reescrita, decisión temática, análisis, filtro determinista, revisión, propuesta, filtro final, modo de recuperación, resultado bruto, contexto, respuesta y mensajes. Los checkpoints permiten inspeccionar la traza y mantener conversación multiturno.

## 8. Generación de la respuesta

`augmented_generator.py` transforma cualquier `RetrievalResult` en un contexto textual común. El generador recibe la pregunta, ese contexto y el filtro aplicado. El prompt exige:

- responder únicamente con la evidencia recuperada;
- distinguir un resultado vacío de una ausencia absoluta de incendios;
- limitar las afirmaciones al corpus disponible;
- utilizar agregados exactos cuando la ruta es `count` o `min_max`.

La implementación usa directamente el cliente de Ollama y `gemma4:31b-cloud`.

## 9. Calidad, límites y evolución

La batería actual contiene 137 pruebas y usa dobles para evitar depender de Ollama Cloud, BGE-M3 o una base real en la mayoría de los casos.

Limitaciones principales:

- cobertura condicionada por los partes de MITECO;
- identidad de incendio heurística cuando falta la fecha inicial;
- parser todavía no incremental;
- ruta temporal pendiente;
- falta una evaluación sistemática de calidad de recuperación y respuesta;
- falta una política común de reintentos ante JSON inválido del LLM;
- eliminación de registros obsoletos de Chroma pendiente.

El diseño detallado de los nodos y de sus decisiones se conserva en [ARQUITECTURA_LANGGRAPH.md](ARQUITECTURA_LANGGRAPH.md).
