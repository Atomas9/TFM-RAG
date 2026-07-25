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
genera embeddings normalizados con `BAAI/bge-m3` y almacena cada
`snapshot_id`, `chunk_text`, vector y conjunto plano de metadatos en la
coleccion persistente `MITECO_fire_snapshots` de ChromaDB.

La implementacion del alumno continua en `src/miteco_rag/retrieval_chroma.py`.
La solucion de referencia para la recuperacion semantica e hibrida se conserva
por separado en `src/miteco_rag/extras/retrieval_chroma_solution.py`. El analizador
determinista de `src/miteco_rag/query_filters.py` reconoce filtros incluidos y
excluidos de pais, comunidad, provincia, localizacion, estado, situacion
operativa y fecha del parte. Tambien distingue consultas presentes e
historicas: si se pregunta que incendios `hay`, `existen` o estan `activos`
sin indicar fecha, utiliza el ultimo parte disponible.

El MVP de generación está implementado en
`src/miteco_rag/augmented_generator.py`. Formatea los resultados de Chroma,
construye mensajes con instrucciones de grounding y genera la respuesta con
`gemma4:31b-cloud` mediante Ollama. `src/miteco_rag/main.py` conecta por
terminal retrieval, contexto y generación. Si Chroma no devuelve documentos,
se responde de forma controlada sin llamar al LLM.

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

El corpus bruto contiene actualmente trece partes. La validación inicial del
parser y el índice existente se realizaron sobre ocho de ellos: la maquina de
estados delimitó 48 bloques `Localizacion:`, 47 de Espana y uno de Portugal.
Por decision del proyecto, ese indice conserva los 48 registros, incluido el
de Portugal. Los PDF originales de MITECO se versionan; los resultados
procesados y el indice local continúan fuera del control de versiones.

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
7. Recuperacion de contexto y generacion con `gemma4:31b-cloud` mediante
   Ollama.

La decision completa esta documentada en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Estructura

```text
.
├── src/miteco_rag/             Codigo principal
│   └── extras/                 Esqueletos y soluciones de referencia
├── tests/                      Pruebas automatizadas
├── notebooks/                  Apuntes y soluciones ejecutables paso a paso
├── data/
│   ├── raw/miteco/             PDF originales y manifiesto versionados
│   ├── processed/              Registros parseados, no versionados
│   └── chroma/                 Indice vectorial local, no versionado
├── .github/workflows/          Automatizacion diaria de la descarga
├── docs/                       Documentacion tecnica
├── extras/                     Codigo y documentos anteriores de referencia
├── CUADERNO_DE_BITACORA.md     Historial diario del proyecto
├── requirements.txt            Dependencias compatibles
└── .env.example                Variables configurables sin secretos
```

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

La ejecucion utiliza CPU y procesa los textos en lotes de ocho. La primera
carga del modelo puede tardar porque Sentence Transformers debe descargarlo o
recuperarlo de su cache. El script emplea `upsert`: actualiza los IDs que ya
existen e inserta los nuevos, pero no elimina automaticamente posibles IDs
obsoletos que hayan desaparecido del JSONL.

Para inspeccionar tres registros sin generar de nuevo los embeddings:

```bash
python src/miteco_rag/chroma_tests.py
```

Esta utilidad debe ejecutarse desde la raiz del repositorio porque su ruta a
`data/chroma` es relativa al directorio de trabajo.

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

## Siguiente fase

El siguiente incremento añadira el revisor LLM de filtros. El parser
determinista se conservara como linea base y el modelo comprobara si sus
filtros son coherentes y suficientes. Las correcciones se validaran con
Pydantic y se reconciliaran campo por campo antes de construir el `where`.

Después, el workflow de LangGraph elegira entre recuperacion semantica,
hibrida, exhaustiva, recuento o linea temporal. Tras consultar Chroma evaluara
el contexto y permitira como maximo un segundo retrieval antes de responder o
abstenerse.

## Probar el MVP

Con Ollama iniciado y el modelo Cloud disponible:

```bash
python src/miteco_rag/main.py
```

El programa solicita una pregunta, recupera hasta diez chunks y muestra la
respuesta fundamentada. La primera ejecución del embedding puede tardar por la
carga de BGE-M3.

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

La solucion comentada de la primera fase puede estudiarse y ejecutarse desde
[notebooks/01_fase1_parseo_miteco.ipynb](notebooks/01_fase1_parseo_miteco.ipynb).

La ultima revision del codigo desarrollado esta en
[docs/REVISION_FASE_1.md](docs/REVISION_FASE_1.md).

La revision del indice vectorial esta en
[docs/REVISION_EMBEDDINGS_CHROMA.md](docs/REVISION_EMBEDDINGS_CHROMA.md).

La revision del retrieval hibrido esta en
[docs/REVISION_RETRIEVAL.md](docs/REVISION_RETRIEVAL.md).

La revisión del MVP generador está en
[docs/REVISION_GENERADOR.md](docs/REVISION_GENERADOR.md).

Los apuntes sobre el propósito y el uso de cada dependencia están en
[docs/apuntes/LIBRERIAS.md](docs/apuntes/LIBRERIAS.md).
