# Proceso de desarrollo del RAG de incendios de MITECO

Este documento explica de forma resumida y ordenada cómo se ha construido el
proyecto. Está pensado para entender el recorrido completo sin tener que leer
la bitácora diaria ni revisar todos los commits.

La bitácora responde a «¿qué se hizo cada día?». Este documento responde a
«¿cómo funciona el proyecto, por qué se tomaron estas decisiones y cómo hemos
llegado hasta aquí?».

## 1. Objetivo del proyecto

El objetivo es crear un sistema RAG capaz de responder preguntas sobre los
partes diarios de actuaciones en incendios forestales publicados por MITECO.

El sistema debe permitir dos tipos de búsqueda:

- búsqueda semántica, para encontrar incendios relacionados con el significado
  de una pregunta;
- búsqueda por metadatos, para aplicar condiciones exactas como provincia,
  comunidad autónoma, localización, estado o fecha.

El flujo general construido hasta ahora es:

```text
PDF de MITECO
      ↓
extracción y limpieza del texto
      ↓
separación de cada incendio
      ↓
FireSnapshot + chunk_text + metadatos
      ↓
fire_snapshots.jsonl
      ↓
embeddings BGE-M3
      ↓
colección persistente de ChromaDB
      ↓
búsqueda semántica + filtros de metadatos
```

El primer MVP ya genera una respuesta final mediante Ollama Cloud. La siguiente
fase revisará los filtros con un LLM y orquestará progresivamente el workflow
con LangGraph.

## 2. Preparación del repositorio y del entorno

El proyecto se reorganizó para separar el código nuevo del material anterior.
Los documentos y programas utilizados como referencia se conservaron en
`extras`, mientras que la implementación principal se situó en
`src/miteco_rag`.

Se creó el entorno Conda `RAG-TFM` con Python 3.11. Las versiones de NumPy,
PyTorch y Transformers tuvieron que ajustarse para mantener compatibilidad con
el Mac Intel utilizado durante el desarrollo.

Los PDF originales, los JSONL procesados y el índice de Chroma no se incluyen
en Git. Son datos locales y regenerables. El repositorio solo conserva el
código, las pruebas y la documentación necesarios para reconstruirlos.

## 3. Lectura de los PDF

Los partes de MITECO son PDF con una estructura visual pensada para personas,
no para su tratamiento automático. El primer paso fue extraer su texto con
PyMuPDF:

```python
document = pymupdf.open(pdf_path)
```

La extracción conserva el número de página de cada línea. Esto es importante
porque cada respuesta del RAG debe poder indicar de qué documento y página
procede la información.

Después se limpian espacios y caracteres problemáticos y se crea una versión
normalizada para reconocer encabezados y campos sin depender de mayúsculas o
tildes. Se conservan por separado:

- el texto original, útil para trazabilidad;
- el texto limpio, utilizado por el parser;
- el texto normalizado, utilizado para comparar patrones.

## 4. Separación de cada incendio

Un PDF contiene varios incendios. No era adecuado guardar una página o un PDF
completo como un único chunk, porque una búsqueda podría mezclar provincias,
estados y medios de incendios distintos.

La unidad documental elegida es un **snapshot**: el estado de un incendio tal
como aparece en un parte concreto.

El parser recorre las líneas y mantiene el contexto geográfico. Esto es
necesario porque los partes no siempre repiten la comunidad autónoma o la
provincia delante de cada incendio. Cuando aparece una nueva localización se
abre un bloque y se reúnen sus datos hasta encontrar el siguiente incendio.

De cada bloque se extraen, entre otros:

- país;
- comunidad autónoma;
- provincia;
- localización;
- estado;
- situación operativa;
- medios asignados;
- nota;
- posible fecha de inicio;
- fecha del parte;
- archivo y páginas de origen.

El corpus local utilizado durante esta fase contiene ocho PDF y produce 48
snapshots: 47 de España y uno de Portugal. El registro portugués se conserva
en el índice y puede incluirse o excluirse mediante el metadato `country`.

## 5. Validación con Pydantic

Cada incendio se representa mediante el modelo Pydantic `FireSnapshot`.
Pydantic comprueba que los datos tengan la estructura y los tipos esperados
antes de exportarlos.

Por ejemplo, una fecha debe ser una fecha válida, los medios deben respetar su
modelo y los campos obligatorios no pueden desaparecer silenciosamente.

Se utilizan dos identificadores diferentes:

- `snapshot_id`: identifica de forma única un incendio dentro de un parte;
- `incident_key`: intenta relacionar snapshots que podrían corresponder al
  mismo incendio en días diferentes.

`incident_key` es todavía heurístico. Utiliza geografía, localización y fecha
de inicio cuando está disponible. Si MITECO omite esa fecha, dos episodios
distintos en la misma ubicación podrían quedar agrupados o un mismo episodio
podría dividirse.

## 6. Construcción del chunk

El embedding no se calcula directamente sobre las líneas originales. Para cada
snapshot se construye un `chunk_text` autosuficiente y legible:

```text
Fecha del parte: 2026-07-13
País: ES
Comunidad autónoma: Castilla y León
Provincia: León
Localización: VILLABLINO
Estado: ACTIVO
...
Fuente: ActuacionesMITECO..., página 2
```

Incluir los campos principales dentro del texto ayuda a la búsqueda semántica
y permite enviar el chunk directamente al futuro LLM generador. Los mismos
valores se guardan también como metadatos planos para realizar filtros exactos.

## 7. Exportación de la fase de parseo

Al ejecutar:

```bash
python src/miteco_rag/parseo_y_chuncking.py
```

se vuelven a procesar todos los PDF y se generan dos archivos:

### `fire_snapshots.jsonl`

Contiene un `FireSnapshot` por línea. Es la entrada utilizada para construir el
índice vectorial.

### `parser_report.json`

Contiene información sobre la ejecución del parser: documentos procesados,
recuentos, advertencias y errores. Sirve para diagnosticar el pipeline sin
tener que inspeccionar todo el JSONL.

La implementación actual no es incremental: si se añaden nuevos PDF, vuelve a
procesar la carpeta completa y reemplaza las salidas.

## 8. Embeddings y almacenamiento en ChromaDB

El script:

```bash
python src/miteco_rag/embeddings_chroma.py
```

realiza tres operaciones:

1. carga y valida cada línea de `fire_snapshots.jsonl`;
2. convierte cada `chunk_text` en un embedding normalizado con `BAAI/bge-m3`;
3. almacena ID, documento, embedding y metadatos en ChromaDB.

La colección persistente se llama:

```text
MITECO_fire_snapshots
```

Los datos se almacenan localmente en `data/chroma`. Se utiliza `upsert`, por lo
que una nueva ejecución inserta registros desconocidos y actualiza los que ya
comparten ID. No elimina automáticamente registros antiguos que hayan
desaparecido del JSONL.

## 9. Primera búsqueda semántica

La consulta del usuario se convierte en un embedding utilizando el mismo
modelo BGE-M3. Chroma compara ese vector con los documentos almacenados y
devuelve los `top_k` más próximos.

La búsqueda semántica funciona bien para conceptos generales, pero no garantiza
que una palabra como `León` se interprete como una provincia. También puede
recuperar un incendio de otra provincia porque alguno de sus medios procede de
una base situada en León.

Esta observación llevó a añadir filtros exactos de metadatos.

## 10. Búsqueda híbrida y filtros deterministas

El módulo `query_filters.py` interpreta condiciones presentes en la pregunta y
construye el argumento `where` de Chroma.

Actualmente reconoce:

- países, comunidades, provincias y localizaciones conocidas;
- estados y situaciones operativas;
- inclusiones y exclusiones;
- coordinaciones como `León o Palencia`;
- contrastes como `no de León, sino de Palencia`;
- fechas exactas, intervalos, meses y años;
- expresiones de presente e históricas.

Cuando se solicitan varias provincias:

```text
Incendios en León y Palencia
```

el filtro utiliza `$in`, que equivale a León **o** Palencia:

```python
{
    "province_normalized": {
        "$in": ["leon", "palencia"]
    }
}
```

Las condiciones de campos distintos sí se combinan mediante `$and`. Por
ejemplo, `activos en León` exige simultáneamente provincia León y estado
`ACTIVO`.

## 11. Interpretación temporal

El catálogo de metadatos conoce las fechas disponibles y calcula
`latest_report_date`.

Se acordaron las siguientes reglas:

- `¿Qué incendios están activos?` utiliza el último parte disponible;
- `¿Qué incendios hay?` utiliza todos los registros del último parte,
  independientemente de su estado;
- `¿Qué incendios estuvieron activos?` es una consulta histórica;
- `¿Qué incendios estaban activos el 13 de julio?` utiliza esa fecha;
- `¿Qué incendios estuvieron activos en julio?` utiliza todo el mes.

Las palabras `hay`, `existen`, `actualmente`, `ahora`, `hoy`, `a día de hoy`,
`en este momento` y `último parte` se consideran expresiones de presente cuando
no existe una fecha explícita.

El último parte significa la fecha máxima del corpus. No equivale a información
en tiempo real, por lo que la respuesta final deberá indicar siempre la fecha
de referencia.

## 12. Estado actual

En este momento están completadas:

- descarga automática y versionada del parte definitivo diario de MITECO;
- validación de firma, encabezado y fecha interna del PDF;
- manifiesto de ingesta con URL, fecha, tamaño y SHA-256;
- lectura y limpieza de PDF;
- separación de incendios;
- extracción de metadatos;
- validación de snapshots;
- exportación JSONL e informe del parser;
- generación de embeddings;
- almacenamiento persistente en Chroma;
- búsqueda semántica;
- búsqueda híbrida con filtros deterministas;
- revisión LLM estructurada de coherencia y suficiencia de filtros;
- propuesta LLM de filtros para `extend` y `replace`;
- traducción determinista de condiciones y grupos al `where` final;
- clasificación binaria de entrada mediante el bouncer;
- carga única del modelo de embeddings, la colección y el catálogo;
- análisis determinista reutilizable mediante `DeterministicAnalysis`;
- formateo del contexto recuperado;
- generación fundamentada mediante `gemma4:31b-cloud`;
- punto de entrada interactivo por terminal;
- pruebas automatizadas del parser, retrieval y generador.

La suite actual contiene 53 pruebas y puede ejecutarse con:

```bash
python -m pytest -q
```

## 13. Límites conocidos

La versión actual todavía tiene varios límites:

- el parser lingüístico determinista solo entiende las construcciones que se
  han programado;
- las localizaciones exactas proceden del corpus y no de un catálogo completo
  de municipios;
- `top_k` puede devolver resultados de una sola provincia aunque se hayan
  solicitado varias;
- una búsqueda sin resultados no siempre significa que un incendio no
  existiera, sino que no consta en los partes disponibles;
- todavía no se ha calibrado un umbral de distancia semántica;
- el revisor, generador y bouncer todavía no disponen de pruebas automatizadas
  con Ollama simulado;
- la propuesta LLM valida campos, tipos, operadores y fechas, pero todavía no
  comprueba todos los valores contra el catálogo ni detecta duplicados y
  contradicciones entre condiciones;
- Ollama Cloud no aplica actualmente el JSON Schema de `format`, por lo que
  Pydantic puede rechazar una salida no JSON aunque su etiqueta sea correcta;
- el modelo de embeddings y Chroma se cargan antes del bouncer en el `main`
  actual, aunque una respuesta `NO GO` ya no los necesite;
- la identidad entre snapshots de días distintos sigue siendo heurística.

## 14. Siguiente fase: revisión de filtros y LangGraph

La generación de respuestas, el revisor, el generador de filtros y el bouncer
ya funcionan como componentes independientes. La siguiente etapa consolidará
sus contratos mediante pruebas automatizadas, reforzará la validación
determinista y, posteriormente, los conectará mediante un workflow controlado
con LangGraph.

El recorrido previsto será:

```text
clasificación de dominio
        ↓
parser determinista
        ↓
revisión de filtros mediante LLM
        ↓
propuesta LLM cuando falten filtros o sean incorrectos
        ↓
reconciliación y validación determinista
        ↓
selección del tipo de retrieval
        ↓
consulta a Chroma
        ↓
evaluación del contexto
        ↓
respuesta, ausencia documentada o un único reintento
```

El LLM no escribirá directamente el `where` de Chroma. Devolverá una intención
estructurada que será validada con Pydantic, normalizada con los catálogos y
traducida por el constructor determinista.

No se descartarán todos los filtros deterministas porque falle uno ni se
añadirán ciegamente todos los filtros del LLM. La reconciliación conservará los
campos correctos, modificará solo los discutidos y registrará la procedencia de
cada decisión.

El workflow también decidirá si una pregunta necesita ranking semántico,
búsqueda híbrida, todos los registros, un recuento o una evolución temporal.
Después del retrieval distinguirá una consulta exacta sin coincidencias de un
contexto semántico deficiente.

El diseño completo se encuentra en
[ARQUITECTURA_LANGGRAPH.md](ARQUITECTURA_LANGGRAPH.md).

## 15. Archivos principales

| Archivo | Responsabilidad |
| --- | --- |
| `src/miteco_rag/download_miteco_report.py` | Descarga, validación, deduplicación y manifiesto de los partes |
| `src/miteco_rag/parseo_y_chuncking.py` | Lectura, parseo, snapshots y JSONL |
| `src/miteco_rag/embeddings_chroma.py` | Embeddings e indexación |
| `src/miteco_rag/core.py` | Carga única del modelo, la colección y el catálogo |
| `src/miteco_rag/bouncer.py` | Clasificación binaria de entrada `GO`/`NO GO` |
| `src/miteco_rag/query_filters.py` | Interpretación determinista de filtros |
| `src/miteco_rag/revisor_query_filters.py` | Revisión LLM estructurada de los filtros deterministas |
| `src/miteco_rag/generate_filter_LLM.py` | Propuesta LLM, traducción a Chroma y resolución del filtro final |
| `src/miteco_rag/retrieval_chroma.py` | Implementación de retrieval desarrollada durante el aprendizaje |
| `src/miteco_rag/extras/retrieval_chroma_solution.py` | Implementación de referencia |
| `src/miteco_rag/augmented_generator.py` | Contexto y generación con Ollama |
| `src/miteco_rag/main.py` | Punto de entrada del MVP |
| `tests/` | Pruebas automatizadas |
| `CUADERNO_DE_BITACORA.md` | Registro diario detallado |
| `docs/ARQUITECTURA.md` | Decisiones técnicas de arquitectura |
| `docs/ARQUITECTURA_LANGGRAPH.md` | Workflow previsto con LLM y LangGraph |
| `docs/INGESTA_AUTOMATICA_MITECO.md` | Automatización diaria y persistencia del corpus |

## 16. Cómo reconstruir el flujo actual

Con el entorno `RAG-TFM` activado y los PDF en `data/raw/miteco`:

```bash
python src/miteco_rag/parseo_y_chuncking.py
python src/miteco_rag/embeddings_chroma.py
python src/miteco_rag/main.py
```

Para validar el proyecto:

```bash
python -m pytest -q
```

## 17. Refactorización del flujo por consulta

La primera versión cargaba el modelo de embeddings, abría Chroma, reconstruía
el catálogo e interpretaba los filtros desde varias funciones. Esto hacía
difícil seguir qué objeto pertenecía a cada fase y repetía operaciones
costosas.

La carga se centralizó en `core.loader()`:

```python
emb_model, collection, catalog = loader()
```

Estos tres recursos se mantienen durante la ejecución. Para cada nueva
pregunta se construye una sola vez:

```python
analysis = build_deterministic_analysis(query, catalog)
```

`DeterministicAnalysis` conserva:

- `parsed_query`, con texto original y normalizado, filtros y ambigüedades;
- `deterministic_where`, con el diccionario para Chroma o `None`.

El revisor recibe el objeto completo y ya no carga Chroma ni reconstruye el
catálogo. El retrieval recibe el modelo, la colección y el filtro final como
dependencias. `main.py` actúa como orquestador de estas fases.

La trazabilidad estructurada se ha discutido, pero se implementará más
adelante. Se separará el historial conversacional de los eventos técnicos del
pipeline; estos últimos podrán registrarse como JSONL por `run_id` sin
incorporarlos a los mensajes enviados al generador de respuestas.

## 18. Corrección LLM del filtro

Cuando el revisor devuelve `extend` o `replace`,
`generate_filter_llm()` recibe la pregunta, el `DeterministicAnalysis`, el
`FilterReview` y los valores canónicos del catálogo. El modelo no genera código
ni un diccionario libre de Chroma, sino un `FilterProposal`:

```text
FilterProposal
└── groups
    └── FilterGroup: AND u OR
        └── FilterCondition: campo, operador y valor
```

Python comprueba la compatibilidad entre operadores escalares y de lista,
restringe los rangos al campo de fecha y valida fechas reales con formato
`YYYYMMDD`.

```text
FilterCondition
      ↓
condition_to_chroma()
      ↓
FilterGroup
      ↓
group_to_chroma()
      ↓
FilterProposal
      ↓
proposal_to_chroma_where()
      ↓
final_where
```

Las condiciones de un grupo utilizan su `logic`; los grupos diferentes se
combinan mediante `AND`. `resolve_final_where()` conserva el filtro
determinista para `keep`, utiliza la propuesta completa para `extend` y
`replace`, y detiene una continuación automática para `clarify`.

La consulta histórica sobre León y Andalucía produjo un `$or` entre provincia
León y comunidad Andalucía. Chroma aceptó el filtro y recuperó siete snapshots.

## 19. Clasificación inicial con el bouncer

`bouncer.py` ejecuta una decisión binaria antes del análisis de metadatos:

```text
pregunta
   ↓
bouncer
   ├── NO GO → respuesta predeterminada y fin
   └── GO    → análisis, revisión, retrieval y generación
```

El prompt diferencia una petición real sobre los partes de la aparición
aislada de términos como `fuego`, `incendio`, `MITECO` o `BRIF`. El cliente
envía el esquema Pydantic en `format`, pero Ollama Cloud no soporta actualmente
structured outputs. Pydantic mantiene la validación posterior y queda
pendiente definir una recuperación controlada ante texto plano o JSON inválido.

## 20. Primera integración con LangGraph

El pipeline lineal de `main.py` se ha reproducido en `rag_graph.py` como un
grafo de estados. LangGraph no sustituye al parser, Chroma ni las llamadas a
Ollama: organiza en qué orden se ejecutan y qué ruta sigue cada consulta.

```text
START
  │
  ▼
Bouncer
  ├── NO GO ──────────────────────────────> END
  └── GO
       ▼
DeterministicAnalysis
       │
       ▼
Reviewer
  ├── clarify ────────────────────────────> END
  ├── keep ───────────────────────────────> Retrieve
  └── extend / replace ─> GenerateFilter ─> ResolveWhere
                                                │
                                                ▼
                                             Retrieve
                                                │
                                                ▼
                                        GenerateContext
                                                │
                                                ▼
                                         GenerateAnswer
                                                │
                                                ▼
                                               END
```

`GraphState` acumula las salidas de los nodos. En particular, mantiene
`deterministic_where` y `final_where` como campos distintos. De esta forma una
ejecución permite comparar el filtro construido por reglas con el filtro que
finalmente recibió Chroma.

El modelo de embeddings, la colección y el catálogo se cargan una vez mediante
`core.loader()`. No se incluyen en `GraphState` porque son recursos pesados y
no deben serializarse en los checkpoints. Los nodos se mantienen como funciones
externas y `functools.partial` les asigna las dependencias necesarias durante
la construcción del grafo.

`main_langgraph.py` se limita a construir el workflow, asignar un `thread_id`,
invocarlo con la pregunta y mostrar `state["answer"]`. La persistencia se ha
actualizado a `SqliteSaver`, que conserva el historial localmente después de
cerrar el proceso. Esto todavía no hace que el sistema entienda automáticamente
preguntas conversacionales.

La siguiente ampliación separará dos memorias:

- historial conversacional, con las preguntas y respuestas que necesita el
  sistema para interpretar referencias a turnos anteriores;
- traza técnica, con decisiones, filtros, documentos y rutas de cada consulta.

Antes de reutilizar un mismo estado para varias preguntas habrá que impedir que
campos transitorios de una ejecución anterior, como `proposal` o `context`, se
interpreten como resultados de la nueva consulta.

## 21. Deudas descubiertas al persistir e inspeccionar el grafo

La primera lectura de checkpoints confirmó que el estado permite reconstruir
la ruta completa, pero detectó tres tareas previas a ampliar el workflow.

En una primera versión, `GraphState` guardaba directamente modelos Pydantic
como `BouncerDecision`, `DeterministicAnalysis` y `FilterReview`. LangGraph los
deserializaba, pero advertía que eran tipos personalizados no registrados. La
implementación se corrigió: el estado guarda cadenas y diccionarios compatibles
con JSON mediante `model_dump(mode="json")`, y cada nodo reconstruye
temporalmente el modelo necesario mediante `model_validate()`.

La decisión del bouncer se persiste como `GO` o `NO GO`; el análisis, la
revisión y la propuesta se persisten como diccionarios. Las funciones de
negocio conservan sus modelos Pydantic, por lo que no se pierde validación. Las
cuatro rutas principales se comprobaron con SQLite y MsgPack estricto y los
checkpoints pudieron reabrirse sin deserializar clases personalizadas.

En segundo lugar, falta distinguir filtros de metadatos y modo de consulta. Un
`where=None` puede ser completamente correcto y, sin embargo, una búsqueda
semántica `top_k` puede ser la operación equivocada. Las preguntas sobre fecha
máxima, recuentos o todos los incendios requieren agregaciones o consultas
exhaustivas. Se añadirá un nodo `ChooseRetrievalMode` antes de recuperar datos.

En tercer lugar, el inspector llama a `create_graph()` para utilizar
`get_state_history()`. Como esa función ejecuta `loader()`, inspeccionar una
traza carga innecesariamente BGE-M3, Chroma y el catálogo. La utilidad de
inspección se desacoplará de los recursos de inferencia o utilizará directamente
la interfaz del checkpointer.

Completada la serialización segura, el siguiente paso es la selección del modo
de consulta y, después, la optimización del inspector. La conversación
multiturno se construirá sobre ese estado ya estabilizado.
