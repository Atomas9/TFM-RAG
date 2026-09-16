# MITECO Fire RAG

Sistema RAG desarrollado como parte de un TFM para consultar los partes diarios de intervenciones en incendios forestales publicados por MITECO.

El sistema descarga los PDF, separa cada incendio en un registro independiente, extrae metadatos, construye índices complementarios en ChromaDB y SQLite y responde preguntas mediante un flujo conversacional de LangGraph y Ollama Cloud.

> Los partes reflejan actuaciones de medios de MITECO. No constituyen un inventario completo de todos los incendios de España ni una fuente en tiempo real.

## Estado del proyecto

El MVP incluye:

- descarga automática de nuevos partes con GitHub Actions;
- extracción de texto con PyMuPDF y validación mediante Pydantic;
- un `FireSnapshot` por incendio y fecha de parte;
- embeddings multilingües con `BAAI/bge-m3` e indexación incremental en ChromaDB;
- un almacén SQLite para filtros y agregaciones exactas;
- interpretación determinista de filtros y revisión/corrección mediante LLM;
- recuperación híbrida, consultas de mínimo/máximo y recuentos;
- respuestas fundamentadas con `gemma4:31b-cloud` mediante Ollama;
- conversación multiturno y checkpoints persistentes con LangGraph;
- 137 pruebas automatizadas.

Estado del corpus validado el 16 de septiembre de 2026:

| Elemento | Cantidad |
|---|---:|
| Partes PDF | 58 |
| Snapshots | 324 |
| Incendios en España | 318 |
| Registros extranjeros | 6 |
| Primera fecha de parte | 5 de julio de 2026 |
| Última fecha de parte | 7 de septiembre de 2026 |

El parte del 30 de agosto informa de cero actuaciones y se conserva en el informe del parser.

## Arquitectura

```text
MITECO
  -> GitHub Actions / descarga local
  -> PDF en data/raw/miteco
  -> parser y validación
  -> FireSnapshot en JSONL
       ├─> BGE-M3 -> ChromaDB: texto, embedding y metadatos
       └─> SQLite: metadatos para filtros y agregaciones exactas

Pregunta
  -> preparación del turno y reescritura contextual
  -> clasificación temática
  -> filtros deterministas
  -> revisión/corrección opcional con LLM
  -> selección del modo de recuperación
       ├─> híbrido: ChromaDB
       ├─> mínimo/máximo: SQLite + ChromaDB
       └─> recuento: SQLite
  -> construcción del contexto
  -> respuesta fundamentada con Ollama Cloud
```

La unidad documental es `FireSnapshot`: una observación de un incendio en un parte concreto. Incluye el texto enriquecido que se utiliza para la búsqueda, los metadatos estructurados, la fuente y dos identificadores:

- `snapshot_id`: identifica una observación concreta;
- `incident_key`: clave heurística para relacionar snapshots del mismo incendio mediante geografía, localización y, cuando existe, fecha de inicio.

La arquitectura completa se explica en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) y el grafo se detalla en [docs/ARQUITECTURA_LANGGRAPH.md](docs/ARQUITECTURA_LANGGRAPH.md).

## Tecnologías

| Área | Tecnología |
|---|---|
| Lectura de PDF | PyMuPDF |
| Modelado y validación | Pydantic |
| Embeddings | Sentence Transformers y `BAAI/bge-m3` |
| Base vectorial | ChromaDB |
| Consultas exactas | SQLite |
| LLM | Ollama Cloud, `gemma4:31b-cloud` |
| Orquestación | LangGraph |
| Persistencia conversacional | `SqliteSaver` |
| Pruebas | pytest |

## Estructura del repositorio

```text
.
├── .github/workflows/          Descarga automática de partes
├── data/
│   ├── raw/miteco/             PDF y manifiesto versionados
│   ├── processed/              JSONL e informe local del parser
│   ├── chroma/                 Índice vectorial local
│   ├── metadata/               Índice SQLite local
│   └── checkpoints/            Memoria conversacional local
├── docs/                       Arquitectura, ingesta y evolución
├── scripts/                    Utilidades de inspección
├── src/miteco_rag/             Código de la aplicación
├── tests/                      Pruebas automatizadas
├── CUADERNO_DE_BITACORA.md     Registro cronológico del desarrollo
├── requirements.txt            Dependencias fijadas
└── .env.example                Ejemplo de configuración
```

Los artefactos procesados, bases locales, checkpoints y materiales auxiliares se excluyen de Git. Los PDF originales se versionan porque el workflow de descarga los incorpora al corpus del proyecto.

## Instalación

```bash
conda create --name RAG-TFM python=3.11 pip -y
conda activate RAG-TFM
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip check
```

Configura las variables necesarias a partir de `.env.example`. El modelo generativo requiere acceso a Ollama Cloud.

## Construcción de los índices

Para descargar manualmente el parte que corresponda:

```bash
python src/miteco_rag/download_miteco_report.py
```

Para reconstruir el JSONL desde todos los PDF disponibles:

```bash
python src/miteco_rag/parseo_y_chuncking.py
```

Después se actualizan ambos índices:

```bash
python src/miteco_rag/embeddings_chroma.py
python src/miteco_rag/metadata_store.py
```

La indexación de Chroma es incremental: compara la firma de cada snapshot, solo carga BGE-M3 cuando hay registros nuevos o modificados y utiliza `upsert`. El parser todavía vuelve a procesar el corpus completo. La eliminación automática de identificadores obsoletos de Chroma queda pendiente.

Más información sobre la descarga y sus garantías de idempotencia en [docs/INGESTA_AUTOMATICA_MITECO.md](docs/INGESTA_AUTOMATICA_MITECO.md).

## Ejecución

Con el entorno activado y los índices construidos:

```bash
python src/miteco_rag/main_langgraph.py
```

El programa mantiene un mismo `thread_id` durante la sesión, por lo que permite preguntas de seguimiento como:

```text
¿Qué incendios hay registrados en León?
¿Y cuáles de esos seguían activos en el último parte disponible?
```

El flujo decide entre tres recuperaciones operativas:

- `hybrid`: aplica filtros de metadatos y ordena por similitud semántica en ChromaDB;
- `min_max`: SQLite calcula la fecha extrema dentro del conjunto filtrado y Chroma recupera sus documentos;
- `count`: SQLite calcula recuentos exactos de incendios, snapshots o partes.

El modo `timeline` está reconocido por el clasificador, pero su rama de recuperación todavía no está implementada.

## Inspección y pruebas

Las utilidades de `scripts/` permiten revisar los datos sin iniciar la aplicación:

```bash
python scripts/inspect_chroma.py
python scripts/inspect_checkpoints.py
```

Para ejecutar la batería completa:

```bash
python -m pytest -q
```

Los detalles de las pruebas están en [tests/README.md](tests/README.md).

## Limitaciones y trabajo pendiente

- La identidad de incendio es heurística si el parte no aporta fecha de inicio.
- El parser no es incremental, aunque la indexación vectorial sí lo es.
- La rama temporal o de evolución todavía no está implementada.
- Falta una evaluación sistemática con un conjunto estable de preguntas y métricas.
- No existe aún una política común de reintentos ante respuestas JSON inválidas de Ollama.
- Los identificadores obsoletos se detectan, pero no se eliminan automáticamente de Chroma.

## Documentación

- [Arquitectura técnica](docs/ARQUITECTURA.md)
- [Diseño de LangGraph](docs/ARQUITECTURA_LANGGRAPH.md)
- [Ingesta automática](docs/INGESTA_AUTOMATICA_MITECO.md)
- [Proceso de desarrollo](docs/PROCESO_DEL_PROYECTO.md)
- [Datos](data/README.md)
- [Scripts](scripts/README.md)
- [Pruebas](tests/README.md)
- [Cuaderno de bitácora](CUADERNO_DE_BITACORA.md)
