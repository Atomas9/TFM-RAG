# MITECO Fire RAG

Proyecto de TFM para construir un sistema RAG sobre los partes diarios de
actuaciones en incendios forestales publicados por MITECO.

El objetivo inicial es extraer los PDF, identificar cada incendio como una
unidad documental independiente y permitir consultas semanticas y consultas
estructuradas por metadatos como fecha, comunidad autonoma, provincia,
ubicacion o estado del incendio.

## Estado actual

El repositorio contiene la estructura inicial del proyecto y el entorno de
dependencias validado. En `src/miteco_rag/parseo_y_chuncking.py` ya estan
implementadas la lectura y normalizacion, los metadatos documentales, la
maquina de estados geografica y la separacion por incendios. Tambien se han
anadido extractores de localizacion, estado, situacion operativa, notas, fecha
de inicio y medios asignados. Estos datos ya se integran en un `FireSnapshot`
validado por Pydantic, con identificadores reproducibles, texto original y un
`chunk_text` autosuficiente.

La primera version del indice vectorial tambien esta implementada en
`src/miteco_rag/embeddings_chroma.py`. El script carga y valida el JSONL,
detecta los snapshots nuevos o modificados y solo entonces carga `BAAI/bge-m3`
para generar sus embeddings normalizados. Cada registro conserva una firma de
indexacion junto a su `snapshot_id`, `chunk_text`, vector y metadatos en la
coleccion persistente `MITECO_fire_snapshots` de ChromaDB.

La implementacion del alumno continua en `src/miteco_rag/retrieval_chroma.py`.
La solucion de referencia para la recuperacion semantica e hibrida se conserva
por separado en `src/miteco_rag/extras/retrieval_chroma_solution.py`. El analizador
determinista de `src/miteco_rag/query_filters.py` reconoce filtros incluidos y
excluidos de pais, comunidad, provincia, localizacion, estado, situacion
operativa y fecha del parte. Tambien distingue consultas presentes e
historicas: si se pregunta que incendios `hay`, `existen` o estan `activos`
sin indicar fecha, utiliza el ultimo parte disponible.

La recuperación dispone ya de un contrato plano común, `RetrievalResult`. La
búsqueda híbrida utiliza Chroma, mientras que las operaciones exactas utilizan
una base SQLite derivada del JSONL. `retrieve_min_max()` calcula primero el
extremo dentro del conjunto filtrado y recupera después sus documentos por ID;
`retrieve_count()` distingue incendios únicos, snapshots e informes sin cargar
embeddings ni chunks.

El MVP de generación está implementado en
`src/miteco_rag/augmented_generator.py`. Formatea los resultados recuperados,
construye mensajes con instrucciones de grounding y genera la respuesta con
`gemma4:31b-cloud` mediante Ollama. `src/miteco_rag/main_langgraph.py` conecta
por terminal clasificación, filtros, selección del modo de retrieval,
recuperación, contexto y generación. El
generador utiliza `WITH_DATA` cuando recibe documentos o un agregado exacto,
incluido un recuento igual a cero, y `NO_DATA` cuando no hay información
recuperada. Las ausencias se limitan explícitamente al corpus consultado.

El flujo lineal anterior se conserva como referencia académica en
`src/miteco_rag/extras/main_lineal_obsoleto.py`. No cumple el contrato actual
de `core.loader()` ni integra las ramas exactas `min_max` y `count`. El único
punto de entrada vigente del MVP es `main_langgraph.py`.

Durante la revision se corrigieron dos accesos a `clean_text` para utilizar el
atributo correcto, `cleaned_text`. El parser ya completa el recorrido de los
ocho PDF sin errores. La delimitacion de bloques, la construcción de snapshots
y la presencia de los campos se han comprobado, aunque todavia falta validar
manualmente la exactitud de las notas y los medios extraidos y convertir estas
comprobaciones en pruebas pytest.

El material previo utilizado como referencia se conserva en `extras`, pero no
forma parte del codigo principal.

La captura de nuevos partes está automatizada. El módulo independiente
`src/miteco_rag/download_miteco_report.py` descubre el parte definitivo del día
anterior, valida su contenido y fecha, calcula su SHA-256 y lo registra junto a
un manifiesto. GitHub Actions lo ejecuta dos veces al día y crea un commit solo
cuando hay un documento nuevo o una revisión.

El corpus bruto contiene actualmente 55 partes. La salida procesada, Chroma y
SQLite están sincronizados con 309 snapshots hasta el parte del 4 de septiembre
de 2026; el parte del 30 de agosto declara cero actuaciones y se conserva en el
informe del parser con recuento cero. Los PDF originales de MITECO se
versionan; los resultados procesados, Chroma y SQLite continúan fuera del
control de versiones.

`snapshot_id` identifica de forma unica una observacion dentro de un parte.
`incident_key` es una clave heuristica para agrupar observaciones que podrian
pertenecer al mismo incendio: utiliza geografia, localizacion y fecha de inicio
cuando esta existe. No debe interpretarse todavia como una identidad definitiva
si MITECO no proporciona la fecha de inicio.

La orquestacion de la fase ya esta disponible: `parse_miteco_pdf()` transforma
un PDF en sus snapshots y `parse_pdf_directory()` procesa todos los PDF de una
carpeta en orden determinista, sin deduplicar observaciones de dias distintos.
Las rutas inexistentes o las carpetas sin PDF producen errores explicitos.

`run_phase1()` valida el corpus y genera dos artefactos reproducibles:
`data/processed/fire_snapshots.jsonl`, con un snapshot por linea, y
`data/processed/parser_report.json`, con los archivos procesados, recuentos,
advertencias y errores. La importacion del modulo no ejecuta el pipeline; la
escritura solo se produce al ejecutar el archivo como programa.

## Arquitectura prevista

1. Descarga automática, validación y versionado de los PDF de MITECO.
2. Extraccion de texto por paginas con PyMuPDF.
3. Parser basado en la estructura de los partes y en un estado persistente de
   comunidad y provincia.
4. Un registro o snapshot por incendio y fecha de parte.
5. Embeddings multilingues con `BAAI/bge-m3`.
6. Persistencia vectorial y filtrado de metadatos con ChromaDB.
7. Consultas exactas y agregaciones sobre metadatos con SQLite.
8. Recuperacion de contexto y generacion con `gemma4:31b-cloud` mediante
   Ollama.
9. Orquestación controlada, rutas y checkpoints mediante LangGraph.

La decision completa esta documentada en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Estructura

```text
.
├── src/miteco_rag/             Codigo principal
│   └── extras/                 Esqueletos y soluciones de referencia
├── scripts/                    Utilidades manuales de inspeccion
├── tests/                      Pruebas automatizadas
├── notebooks/                  Apuntes y soluciones ejecutables paso a paso
├── data/
│   ├── raw/miteco/             PDF originales y manifiesto versionados
│   ├── processed/              Registros parseados, no versionados
│   ├── chroma/                 Indice vectorial local, no versionado
│   ├── metadata/               Metadatos SQLite locales, no versionados
│   └── checkpoints/            Trazas SQLite locales, no versionadas
├── .github/workflows/          Automatizacion diaria de la descarga
├── docs/                       Documentacion tecnica
│   └── revisiones/             Revisiones historicas por fase
├── extras/                     Codigo y documentos anteriores de referencia
├── CUADERNO_DE_BITACORA.md     Historial diario del proyecto
├── requirements.txt            Dependencias compatibles
└── .env.example                Variables configurables sin secretos
```

Dentro de `src/miteco_rag`, `rag_graph.py` define el estado, los nodos y las
rutas de LangGraph; `main_langgraph.py` es su punto de entrada por terminal.

## Preparar el entorno

```bash
conda create --name RAG-TFM python=3.11 pip -y
conda activate RAG-TFM
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip check
```

El repositorio esta preparado para macOS Intel. `requirements.txt` selecciona
PyTorch 2.2.2 en esa plataforma y una version moderna de PyTorch en las
plataformas que disponen de wheels compatibles.

## Descarga automática y datos

Los PDF de MITECO y su manifiesto sí se versionan en Git. Los resultados
procesados y ChromaDB permanecen excluidos. El workflow
`.github/workflows/download-miteco-report.yml` intenta obtener el parte
definitivo a las 12:37 y 18:17, hora de Madrid, y también puede lanzarse
manualmente desde GitHub.

La descarga local se ejecuta con:

```bash
python src/miteco_rag/download_miteco_report.py
```

Consulta [docs/INGESTA_AUTOMATICA_MITECO.md](docs/INGESTA_AUTOMATICA_MITECO.md)
para conocer la validación, el manifiesto, la idempotencia y las revisiones, y
[data/README.md](data/README.md) para las reglas del corpus.

Para reconstruir la salida procesada completa:

```bash
python src/miteco_rag/parseo_y_chuncking.py
```

La implementacion actual vuelve a procesar todos los PDF y reemplaza los dos
artefactos de `data/processed`. Las salidas procesadas permanecen excluidas de
Git. Los PDF fuente se conservan en el repositorio porque no son artefactos
regenerables del proyecto.

## Generar el indice vectorial

Con el entorno `RAG-TFM` activado y el JSONL ya generado:

```bash
python src/miteco_rag/embeddings_chroma.py
```

La ejecucion utiliza CPU y procesa los textos pendientes en lotes de ocho. La
primera ejecucion tras incorporar la indexacion incremental recalcula una vez
la coleccion anterior para guardar `index_signature`. A partir de la segunda,
si nada ha cambiado, termina sin cargar BGE-M3. El script emplea `upsert` y
detecta posibles IDs obsoletos, pero por ahora solo informa de ellos y no los
elimina automaticamente.

Para inspeccionar tres registros sin generar de nuevo los embeddings:

```bash
python scripts/inspect_chroma.py
```

La utilidad calcula la ruta desde su propio archivo, no genera embeddings y
cierra el cliente de Chroma al terminar.

## Consultar el indice

La demostracion incluida ejecuta una consulta semantica combinada con los
filtros detectados:

```bash
PYTHONPATH=src python -m miteco_rag.extras.retrieval_chroma_solution
```

Desde Python, con `src` incluido en `PYTHONPATH`:

```python
from miteco_rag.extras.retrieval_chroma_solution import retrieve_with_filters

results, parsed_query, where = retrieve_with_filters(
    "Incendios activos en Leon",
    top_k=5,
)
```

`parse_metadata_filters()` separa la interpretacion del lenguaje natural y
`build_chroma_where()` genera la condicion de Chroma. Se soportan inclusiones,
exclusiones, listas, contrastes como `no de Leon sino de Palencia`, fechas
exactas, meses, anos y rangos. Las expresiones de presente como `hay`,
`actualmente`, `ahora`, `a dia de hoy` o `ultimo parte` seleccionan la fecha
maxima del corpus. Las formas historicas como `estuvieron activos` conservan
todos los partes si no se especifica otro periodo. Las comunidades y
provincias proceden de catalogos controlados; las localizaciones se obtienen de
los metadatos de la coleccion. La funcion de conveniencia
`metadata_query(question, catalog)` unifica ambos pasos y devuelve directamente
el valor que debe recibir `where`.

Las pruebas del analizador y de su integracion se ejecutan sin cargar el modelo:

```bash
python -m pytest -q
```

El primer revisor LLM de filtros está implementado en
`src/miteco_rag/revisor_query_filters.py`. Compara la pregunta con los filtros,
ambigüedades y `where` deterministas y devuelve un `FilterReview` estructurado
con las acciones `keep`, `extend`, `replace` o `clarify`. Cuatro pruebas reales
con `gemma4:31b-cloud` validaron filtros correctos, un `AND` geográfico
incorrecto, una contradicción y una consulta puramente semántica.

El flujo se ha refactorizado para cargar una sola vez los recursos constantes
de una ejecución. `src/miteco_rag/core.py` devuelve el modelo de embeddings, la
colección de Chroma y el catálogo de metadatos. Para cada pregunta,
`build_deterministic_analysis()` produce un único `DeterministicAnalysis` con
el `ParsedQuery` y su `deterministic_where`; este objeto se reutiliza en el
revisor y evita reconstruir el catálogo o interpretar varias veces la misma
consulta. `retrieval_chroma.py` recibe ahora el modelo, la colección y el
filtro ya preparados.

El generador de filtros LLM ya está conectado para las acciones `extend` y
`replace`. Devuelve un `FilterProposal` validado con Pydantic, formado por
condiciones y grupos lógicos `AND/OR`. Python valida operadores y fechas,
traduce la propuesta a sintaxis de Chroma y selecciona el `where` final.

También se ha añadido `src/miteco_rag/bouncer.py`, un clasificador binario
`GO`/`NO GO` que detiene preguntas claramente ajenas a los partes. Su prompt
clasifica la intención principal y no la mera presencia de palabras como
`fuego` o `MITECO`.

El mismo pipeline ya dispone de una primera orquestación con LangGraph en
`src/miteco_rag/rag_graph.py`. El estado conserva por separado el filtro
determinista y el filtro final; los nodos reutilizan las funciones existentes
y las rutas distinguen `NO GO`, `keep`, `extend`, `replace` y `clarify`. Tras
resolver el filtro, otro nodo selecciona `hybrid`, `min_max`, `count` o la
intención todavía pendiente `timeline`. Las tres ramas implementadas convergen
en los mismos nodos de contexto y respuesta. Los
recursos pesados se cargan una sola vez al construir el grafo y se inyectan en
los nodos mediante `functools.partial`, sin guardarlos en el estado. El punto
de entrada `src/miteco_rag/main_langgraph.py` mantiene una conversación por
terminal y utiliza `SqliteSaver` para conservar sus mensajes y checkpoints
localmente en `data/checkpoints/langgraph.sqlite`. Antes de cada turno,
`prepare_turn.py` limpia el estado técnico anterior y `rewrite_query.py`
convierte referencias como `allí`, `ese día` o `ambas provincias` en una
consulta autosuficiente.

## Siguiente fase

Queda pendiente convertir las comprobaciones manuales del revisor, generador y
bouncer en pruebas automatizadas con Ollama simulado. La validación del filtro
propuesto deberá ampliarse para comprobar valores canónicos contra el catálogo,
condiciones contradictorias y duplicados.

Ollama Cloud no garantiza actualmente el cumplimiento del JSON Schema enviado
mediante `format`. Los prompts muestran el JSON exacto y Pydantic valida las
respuestas, pero todavía debe decidirse una política controlada de reintento o
normalización cuando el modelo devuelva una etiqueta válida como texto plano.

Los valores persistidos en `GraphState` ya son serializables de forma explícita
y segura. Los modelos Pydantic se convierten mediante
`model_dump(mode="json")` antes de entrar en el estado y se reconstruyen con
`model_validate()` únicamente dentro de los nodos que los necesitan. Las rutas
`NO GO`, `keep`, `replace` y `clarify` se han validado con SQLite y MsgPack en
modo estricto, sin deserializar clases personalizadas.

El selector determinista `choose_retrieval_mode()` y las recuperaciones
`min_max` y `count` ya están integrados en LangGraph. La búsqueda vectorial
`top_k` queda reservada para el modo híbrido; SQLite resuelve los extremos y
recuentos después de aplicar `final_where`. La conexión de metadatos se abre en
el punto de entrada, se inyecta en los nodos y se cierra al terminar, igual que
el cliente persistente de Chroma.

El inspector de checkpoints también está desacoplado de `create_graph()` y lee
directamente `SqliteSaver`, por lo que ya no carga BGE-M3, Chroma ni el
catálogo. El routing de `hybrid`, `min_max` y `count` está cubierto mediante
pruebas aisladas que también verifican la convergencia posterior y las salidas
anticipadas. El orden de trabajo actualizado es:

1. ~~Hacer incremental la indexación vectorial de Chroma.~~
2. Hacer incremental el parseo mediante SHA-256 del PDF y `parser_version`, y
   definir la eliminación de registros obsoletos en informes revisados.
3. Hacer incremental, si resulta necesario, la sincronización de SQLite; su
   `upsert` completo actual no recalcula embeddings y sigue siendo barato.
4. Medir los costes de carga, retrieval y llamadas a Ollama antes de aplicar
   otras optimizaciones.

La conversación multiturno ya está integrada y cubierta por pruebas. Después
se abordarán la validación defensiva de salidas LLM, la evaluación del contexto
y el modo `timeline`. El flujo lineal obsoleto ya se conserva en `extras`.

## Probar el MVP

Con Ollama iniciado y el modelo Cloud disponible, el punto de entrada vigente
es la versión orquestada mediante LangGraph:

```bash
python src/miteco_rag/main_langgraph.py
```

El programa mantiene un bucle de conversación hasta que se escribe `salir` y
reutiliza el mismo `thread_id` en todos los turnos. En modo híbrido recupera
hasta diez chunks; `min_max` recupera los documentos de la fecha extrema y
`count` devuelve un agregado exacto. La primera ejecución del embedding puede
tardar por la carga de BGE-M3. El bouncer puede detener la consulta; `keep`
conserva el
`deterministic_where`; `extend` y `replace` generan y traducen una propuesta
nueva; `clarify` muestra los problemas detectados y termina antes del
retrieval.

`main_langgraph.py` conserva además en `GraphState` los mensajes, la pregunta
original y su reescritura, la decisión del bouncer, el análisis, la revisión,
la propuesta opcional, los filtros determinista y final, el resultado de
recuperación, el contexto y la respuesta. `SqliteSaver` persiste los
checkpoints en `data/checkpoints/langgraph.sqlite`.

Las consultas sobre el presente se limitan a la fecha máxima realmente
disponible en el catálogo. Esa fecha viaja dentro de
`DeterministicAnalysis`, de modo que el revisor LLM puede reconocer su origen
y no confundirla con la fecha actual del calendario. El bouncer también acepta
consultas implícitas del dominio como `¿Cuál es la última fecha registrada en
León?`, aunque no repitan la palabra `incendio`.

Las versiones lineales y didácticas anteriores están archivadas en
`src/miteco_rag/extras/` y no deben utilizarse como puntos de entrada.

## Alcance inicial

- Fuente documental: partes diarios de MITECO.
- Cobertura: incendios de Espana.
- Chunking: un incendio por unidad semantica, con subdivision solo si un
  registro supera el limite del modelo de embeddings.
- Recuperacion: semantica, por metadatos y combinada.
- Generacion: respuestas fundamentadas con referencia al documento, fecha y
  pagina.

## Seguimiento

Las decisiones y avances diarios se registran en
[CUADERNO_DE_BITACORA.md](CUADERNO_DE_BITACORA.md).

Una explicación más narrativa y resumida de todo el proceso está disponible en
[docs/PROCESO_DEL_PROYECTO.md](docs/PROCESO_DEL_PROYECTO.md).

La arquitectura acordada para el workflow con LLM y LangGraph se documenta en
[docs/ARQUITECTURA_LANGGRAPH.md](docs/ARQUITECTURA_LANGGRAPH.md).

La revisión del primer revisor LLM y sus pruebas pendientes se documenta en
[docs/revisiones/REVISION_REVISOR_QUERY_FILTERS.md](docs/revisiones/REVISION_REVISOR_QUERY_FILTERS.md).

La revisión del filtro LLM, su traducción determinista y el bouncer está en
[docs/revisiones/REVISION_FILTRO_LLM_Y_BOUNCER.md](docs/revisiones/REVISION_FILTRO_LLM_Y_BOUNCER.md).

La solucion comentada de la primera fase puede estudiarse y ejecutarse desde
[notebooks/01_fase1_parseo_miteco.ipynb](notebooks/01_fase1_parseo_miteco.ipynb).

La ultima revision del codigo desarrollado esta en
[docs/revisiones/REVISION_FASE_1.md](docs/revisiones/REVISION_FASE_1.md).

La revision del indice vectorial esta en
[docs/revisiones/REVISION_EMBEDDINGS_CHROMA.md](docs/revisiones/REVISION_EMBEDDINGS_CHROMA.md).

La revision del retrieval hibrido esta en
[docs/revisiones/REVISION_RETRIEVAL.md](docs/revisiones/REVISION_RETRIEVAL.md).

La revisión del MVP generador está en
[docs/revisiones/REVISION_GENERADOR.md](docs/revisiones/REVISION_GENERADOR.md).

Los apuntes sobre el propósito y el uso de cada dependencia están en
[docs/apuntes/LIBRERIAS.md](docs/apuntes/LIBRERIAS.md).
