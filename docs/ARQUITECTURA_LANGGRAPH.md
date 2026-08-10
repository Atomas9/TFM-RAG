# Arquitectura del workflow RAG con LangGraph

Fecha de decisión: 2026-07-23. Primera implementación: 2026-08-03.

Este documento define la arquitectura acordada para incorporar LLM al RAG de
incendios de MITECO. La primera versión funcional del grafo ya implementa la
clasificación, el análisis determinista, la revisión de filtros, la corrección
opcional, el retrieval y la generación. Las ramas de evaluación de contexto,
reintento y conversación descritas más adelante siguen siendo evolución
prevista.

El sistema se construirá como un **workflow controlado con LangGraph**. No todos
los nodos utilizarán inteligencia artificial: las operaciones que puedan
resolverse de forma segura, reproducible y comprobable continuarán siendo
deterministas.

## 1. Objetivos

El workflow deberá:

- rechazar preguntas claramente ajenas al dominio;
- mantener el parser determinista de metadatos como línea base;
- utilizar un LLM para revisar y completar la interpretación;
- impedir que el LLM construya directamente filtros libres de Chroma;
- reconciliar filtros campo por campo y conservar su procedencia;
- elegir el tipo de recuperación adecuado para cada pregunta;
- distinguir una ausencia real de coincidencias de un contexto semántico malo;
- permitir como máximo un segundo retrieval;
- generar respuestas fundamentadas en los documentos recuperados;
- mantener un estado auditable durante todo el recorrido.

## 2. Principios de diseño

### LangGraph como workflow, no como agente libre

LangGraph conectará nodos y decidirá las rutas mediante aristas condicionales.
El LLM no podrá llamar herramientas o repetir consultas indefinidamente.

### IA solo donde aporta valor

Seguirán siendo deterministas:

- el parser actual;
- la normalización de metadatos;
- la validación Pydantic;
- la detección de contradicciones;
- la reconciliación de filtros;
- la construcción del `where`;
- la llamada a Chroma;
- los límites de reintentos.

Los LLM se utilizarán para:

- clasificar preguntas difíciles;
- revisar la interpretación lingüística;
- proponer información que no detecten las reglas;
- evaluar aspectos semánticos del contexto;
- reformular una consulta cuando proceda;
- redactar la respuesta final.

### Salidas estructuradas y validadas

Los LLM devolverán objetos conceptuales como `QueryIntent`,
`FilterReview` o `ContextEvaluation`. No devolverán código ni diccionarios
`where` que se ejecuten directamente.

### Trazabilidad

El estado conservará la pregunta, los filtros deterministas, la revisión del
LLM, los filtros finales, la procedencia de cada campo, los documentos
recuperados y el motivo de cada bifurcación.

## 3. Grafo general

```text
START
  │
  ▼
deterministic_parse
  │
  ▼
review_query_with_llm
  │
  ├── unrelated/out_of_scope ──> reject ──> END
  ├── ambiguous ───────────────> clarify ─> END
  └── related
          │
          ▼
reconcile_and_validate_filters
          │
          ▼
choose_retrieval_mode
          │
          ▼
retrieve_from_chroma
          │
          ▼
evaluate_context
  │
  ├── sufficient ──────────────> generate_answer ──> END
  ├── no_matching_records ─────> no_data_answer ───> END
  ├── insufficient + intento 0 ─> replan_query
  │                                  │
  │                                  └──> retrieve_from_chroma
  └── insufficient + intento 1 ─> limited_answer ──> END
```

Este flujo incorpora un único ciclo. Tras una recuperación insuficiente se
puede reformular y consultar otra vez, pero el segundo resultado debe terminar
en respuesta o abstención.

## 4. Comparación de interpretaciones

Durante el desarrollo se conservarán de manera independiente el resultado
determinista y la revisión del LLM:

```text
                    ┌── deterministic_parse ──┐
Pregunta normalizada┤                         ├── reconcile_and_validate
                    └────── llm_review ───────┘
```

La ejecución no tiene que ser físicamente paralela desde la primera versión.
Lo importante es que ambas interpretaciones se almacenen por separado para
poder compararlas y evaluarlas.

## 5. Estado compartido

El estado de LangGraph tendrá, como mínimo, estos grupos de información:

```python
class RAGState(TypedDict):
    # Entrada
    question: str
    normalized_question: str

    # Interpretación
    deterministic_filters: MetadataFilters | None
    deterministic_ambiguities: list[str]
    llm_review: FilterReview | None
    resolved_filters: MetadataFilters | None
    filter_provenance: dict[str, str]
    filter_warnings: list[str]

    # Plan de recuperación
    semantic_query: str
    where: dict | None
    retrieval_mode: str
    top_k: int

    # Resultado
    ids: list[str]
    documents: list[str]
    metadatas: list[dict]
    distances: list[float]

    # Control
    retrieval_attempts: int
    context_status: str
    errors: list[str]

    # Salida
    final_answer: str | None
```

La definición definitiva podrá dividir modelos internos y estado del grafo,
pero estos datos deben conservarse para permitir auditoría y pruebas.

## 6. Nodos del workflow

### 6.1. `deterministic_parse`

Ejecuta el parser actual:

```python
parse_metadata_filters(question, catalog)
```

Produce filtros, ambigüedades y el análisis temporal conocido. No abre Chroma
para recuperar documentos ni llama al LLM.

El parser determinista se mantiene porque es rápido, explicable, reproducible
y fiable en los casos cubiertos por pruebas.

### 6.2. `review_query_filters`

Este componente ya está implementado como función independiente en
`revisor_query_filters.py`. Recibe la pregunta y el análisis determinista y
devuelve un `FilterReview` validado:

```python
class FilterReview(BaseModel):
    action: Literal["keep", "extend", "replace", "clarify"]
    coherent: bool
    sufficient: bool
    issues: list[str]
    explanation: str
```

El revisor no clasifica el dominio, no genera todavía los filtros corregidos y
no consulta Chroma. Las cuatro acciones permiten conservar los filtros,
ampliarlos, sustituir una interpretación incorrecta o pedir aclaración.

Las pruebas reales iniciales cubrieron `keep`, `replace`, `clarify` y una
consulta semántica con `where=null`. Quedan pendientes las pruebas
automatizadas con Ollama y Chroma simulados, incluido el caso `extend`.

### 6.3. `generate_filter_proposal`

Está implementado como función independiente y se ejecuta únicamente para
`extend` o `replace`. Devuelve una intención Pydantic con campos, operadores y
grupos lógicos `AND/OR`; no escribe directamente un diccionario libre de
Chroma.

El código determinista ya comprueba campos permitidos, compatibilidad básica
entre operadores y valores, y fechas, y traduce condiciones y grupos al
`where`. Quedan pendientes la validación completa contra catálogo, los
duplicados y las contradicciones internas.

### 6.4. `classify_domain`

La primera versión se ha implementado en `bouncer.py` como componente
independiente del revisor mediante una decisión binaria:

```python
Literal["GO", "NO GO"]
```

`GO` permite continuar y `NO GO` devuelve un rechazo predeterminado. El prompt
evalúa la intención principal y no acepta palabras aisladas como prueba de
pertenencia al dominio.

Una versión posterior podrá sustituir esta decisión por la taxonomía más rica
prevista originalmente:

```python
Literal[
    "miteco_fire_related",
    "fire_related_but_out_of_scope",
    "unrelated",
    "uncertain",
]
```

Ejemplos:

| Pregunta | Clasificación |
| --- | --- |
| ¿Qué incendios hay en León? | `miteco_fire_related` |
| ¿Cómo apago un fuego en una sartén? | `fire_related_but_out_of_scope` |
| ¿Cuál es la capital de Francia? | `unrelated` |
| ¿Se cortó la carretera de Villablino? | `uncertain` |

Solo las preguntas claramente ajenas o fuera del alcance producirán un rechazo
inmediato. Las inciertas podrán continuar o solicitar una aclaración.

### 6.5. `reject`

Devuelve un mensaje predeterminado cuando la pregunta no está relacionada con
el ámbito del RAG:

> Este sistema está especializado en los partes de incendios forestales de
> MITECO y no dispone de información para responder esa pregunta.

El texto definitivo se decidirá al implementar la interfaz.

### 6.6. `clarify`

Solicita una aclaración cuando la pregunta admite interpretaciones
incompatibles y no es seguro escoger una.

No se utilizará la similitud semántica para ocultar una ambigüedad importante.

### 6.7. `reconcile_and_validate_filters`

Es un nodo determinista. Compara los filtros originales y la propuesta del LLM
campo por campo.

No se aplicarán estas reglas simplistas:

- descartar todos los filtros deterministas si uno es incorrecto;
- añadir todos los filtros del LLM cuando falte alguno.

La reconciliación conservará los campos correctos y sustituirá o añadirá solo
los que correspondan.

Ejemplo:

```text
Pregunta:
    Incendios de León que ardían durante julio

Parser determinista:
    provincia = León
    fecha = julio

Revisión LLM:
    falta estado ACTIVO
    la consulta es histórica

Resultado:
    provincia = León                [determinista]
    fecha = 01/07–31/07             [determinista]
    estado = ACTIVO                 [LLM]
```

La salida conservará la procedencia:

```python
class ResolvedFilters(BaseModel):
    filters: MetadataFilters
    provenance: dict[
        str,
        Literal["deterministic", "llm", "combined"],
    ]
    warnings: list[str]
```

Reglas iniciales de reconciliación:

- mantener entidades geográficas explícitas detectadas exactamente;
- mantener negaciones explícitas salvo contradicción demostrable;
- mantener fechas explícitas válidas;
- permitir que el LLM complete interpretaciones implícitas;
- impedir que un valor quede incluido y excluido simultáneamente;
- marcar como ambigua una incompatibilidad que no pueda resolverse;
- normalizar y validar todos los valores antes de continuar.

Después de reconciliar:

```python
where = build_chroma_where(resolved_filters.filters)
```

El LLM nunca construye ni ejecuta directamente ese diccionario.

### 6.8. `choose_retrieval_mode`

Selecciona el tipo de recuperación según la intención de la pregunta:

```python
Literal[
    "semantic_ranked",
    "hybrid_ranked",
    "metadata_exhaustive",
    "count",
    "timeline",
]
```

| Pregunta | Modo previsto |
| --- | --- |
| Incendios parecidos al de Villablino | `semantic_ranked` |
| Incendios activos relevantes en León | `hybrid_ranked` |
| Todos los incendios de León | `metadata_exhaustive` |
| ¿Cuántos incendios hubo en julio? | `count` |
| ¿Cómo evolucionó Villablino? | `timeline` |

Esto evita utilizar siempre `top_k`. Las preguntas sobre todos los registros,
recuentos o evoluciones necesitan `collection.get()` o una recuperación
específica, no únicamente vecinos semánticos.

### 6.9. `retrieve_from_chroma`

Ejecuta el plan validado:

- `collection.query()` para ranking semántico o híbrido;
- `collection.get()` para recuperación exhaustiva y recuentos;
- recuperación y orden temporal para evoluciones.

El nodo registra el `where`, modo, número de resultados, IDs, distancias y
metadatos devueltos.

### 6.10. `evaluate_context`

Evalúa el resultado antes de permitir la generación. Primero ejecutará
comprobaciones deterministas y solo utilizará un LLM cuando sea necesario
evaluar aspectos semánticos.

Estados posibles:

```python
Literal[
    "sufficient",
    "no_matching_records",
    "poor_semantic_match",
    "incomplete_coverage",
    "ambiguous_question",
]
```

#### Contexto suficiente

Los documentos cumplen los filtros y contienen información apropiada para
responder.

#### Sin coincidencias exactas

Un `where` válido devuelve cero documentos. Esto no se interpreta
automáticamente como un error de retrieval ni autoriza a quitar filtros.

Ejemplo:

> No constan incendios de Palencia en el último parte disponible del corpus.

#### Mala coincidencia semántica

Se obtienen vecinos, pero sus distancias o contenidos no justifican una
respuesta. Puede activarse la reformulación.

#### Cobertura incompleta

Se solicitan varias entidades, pero el `top_k` no contiene todas. Antes de
afirmar que una provincia carece de registros, se comprobará con `get()` o con
consultas separadas.

### 6.11. `replan_query`

Solo se alcanza si:

- el contexto es insuficiente;
- la ausencia no es una respuesta exacta válida;
- `retrieval_attempts == 1`.

Puede proponer:

- una consulta semántica reformulada;
- un modo de retrieval diferente;
- un `top_k` distinto;
- consultas separadas por entidad;
- filtros corregidos y nuevamente validados.

Después vuelve a `retrieve_from_chroma`. No puede iniciarse un tercer
retrieval.

### 6.12. `generate_answer`

Recibe la pregunta, los filtros finales y el contexto considerado suficiente.

La respuesta deberá:

- utilizar únicamente información respaldada por el contexto;
- indicar la fecha de referencia;
- distinguir el último parte disponible de la actualidad real;
- citar archivo y página;
- reconocer explícitamente las limitaciones del corpus;
- no afirmar inexistencia histórica a partir de una ausencia en `top_k`.

### 6.13. `no_data_answer`

Responde de forma controlada cuando una consulta exacta no tiene coincidencias.
No necesita inventar una consulta más amplia ni presentar incendios de otra
ubicación.

### 6.14. `limited_answer`

Si el contexto sigue siendo insuficiente tras el segundo retrieval, el sistema
se abstiene o responde solo la parte respaldada, explicando la limitación.

## 7. Ramas de evaluación del contexto

```text
retrieve_from_chroma
          │
          ▼
 evaluate_context
   ┌──────┼───────────────┬──────────────────────┐
   │      │               │                      │
suficiente  cero exacto  contexto pobre     cobertura incompleta
   │      │               │                      │
responder no_data    ¿queda reintento?       comprobar entidades
                         │                      con get()
                    ┌────┴────┐                  │
                    │         │                  └── evaluar otra vez
                   sí         no
                    │         │
                reformular  respuesta limitada
                    │
                    └── segundo y último retrieval
```

## 8. Control de costes y llamadas al LLM

La separación conceptual en nodos no implica utilizar un modelo diferente en
cada uno.

El diseño mantiene funciones independientes para poder evaluarlas y
reemplazarlas. No todas se ejecutan en todas las preguntas:

1. clasificación de dominio;
2. revisión de filtros;
3. propuesta de intención solo para `extend` o `replace`;
4. evaluación o reformulación solo ante un contexto difícil;
5. generación de la respuesta.

Las preguntas fuera de dominio terminan tras la clasificación. Las consultas
con filtros válidos no llaman al generador de intención y las consultas simples
no requieren reformulación. Más adelante se medirá si conviene combinar
clasificación y revisión para reducir latencia y coste.

## 9. Ollama Cloud y validación

Ollama Cloud permite utilizar modelos que no caben en el equipo local. La
primera implementación con `gemma4:31b-cloud` ha devuelto correctamente
respuestas conforme al JSON Schema de `FilterReview`.

La integración utiliza:

1. instrucciones explícitas y datos de entrada serializados como JSON;
2. `format=FilterReview.model_json_schema()`;
3. temperatura cero;
4. validación mediante `model_validate_json()`.

Queda pendiente probar respuestas inválidas y decidir si se permitirá un único
intento controlado de reparación antes de utilizar el parser determinista o
devolver un error.

## 10. Persistencia y memoria

La implementación utiliza `SqliteSaver` y un `thread_id`. Los checkpoints se
conservan localmente después de cerrar Python, pero esto no crea por sí solo
memoria conversacional. Más adelante se utilizará esa persistencia para
preguntas consecutivas:

```text
Usuario: ¿Qué incendios hay en Castilla y León?
Usuario: ¿Y cuáles están activos?
```

En ese caso el estado conversacional deberá resolver que `cuáles` conserva el
ámbito geográfico de la pregunta anterior. También deberá separar los mensajes
que necesita el LLM de la traza técnica de nodos, filtros y documentos.

La memoria se incorporará después de validar correctamente consultas
independientes.

## 11. Evaluación académica

Se creará un conjunto de preguntas con:

- clasificación de dominio esperada;
- filtros esperados;
- tipo de retrieval esperado;
- documentos o recuentos esperados;
- decisión de suficiencia esperada;
- respuesta o abstención esperada.

Se compararán:

1. parser determinista;
2. parser LLM;
3. resultado reconciliado;
4. retrieval final.

Las métricas podrán incluir precisión de entidades, exactitud de filtros,
cobertura, tasa de consultas inválidas, número medio de llamadas al LLM y
porcentaje de respuestas correctamente fundamentadas.

## 12. Orden de implementación acordado

No se implementará todo el grafo a la vez.

1. ~~Definir el modelo Pydantic de revisión.~~
2. ~~Implementar el revisor LLM como función independiente.~~
3. Añadir pruebas simuladas para las cuatro acciones, JSON inválido y entrada
   vacía.
4. ~~Completar la intención Pydantic con condiciones y grupos lógicos.~~
5. ~~Implementar el generador LLM de filtros para `extend` y `replace`.~~
6. Ampliar la validación y reconciliación deterministas de las propuestas.
7. ~~Implementar la primera versión binaria del clasificador de dominio.~~
8. Crear un conjunto inicial de preguntas de evaluación.
9. ~~Corregir los imports internos y construir `rag_graph.py`.~~
10. Serializar de forma segura los modelos Pydantic almacenados en el estado.
11. Añadir la selección de modo de retrieval.
12. Desacoplar el inspector de checkpoints de BGE-M3 y Chroma.
13. Añadir evaluación de contexto y un único reintento.
14. ~~Incorporar generación fundamentada.~~
15. Incorporar historial conversacional.

## 13. Decisiones pendientes

Quedan por determinar mediante experimentación:

- evaluación comparativa del modelo concreto de Ollama Cloud;
- evolución del prompt y de los esquemas;
- criterio para activar `clarify`;
- umbral de mala similitud semántica;
- tamaño inicial de `top_k`;
- política de recuperación por cada entidad solicitada;
- contrato de `ChooseRetrievalMode` para agregaciones, recuentos y consultas
  exhaustivas;
- formato final de citas;
- almacenamiento de trazas y resultados de evaluación.

La traza técnica ya se persiste mediante checkpoints SQLite. Antes de ampliar
su uso se convertirán los modelos Pydantic del estado en datos serializables de
forma explícita. El historial conversacional permanecerá en `messages` y no se
mezclará con las decisiones técnicas de cada fase.

## 14. Referencias

- [LangGraph: workflows y agentes](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph: Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph: persistencia](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Ollama: Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama Cloud](https://docs.ollama.com/cloud)
