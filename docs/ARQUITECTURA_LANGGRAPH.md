# Workflow RAG con LangGraph

Primera decisión de arquitectura: 23 de julio de 2026. Primera implementación: 3 de agosto de 2026. Estado actualizado: 16 de septiembre de 2026.

Este documento describe el grafo ejecutable de `src/miteco_rag/rag_graph.py`. LangGraph se utiliza como workflow controlado: organiza funciones deterministas y llamadas al LLM, conserva el estado y decide las ramas, pero no delega el control completo a un agente autónomo.

## 1. Objetivos

- Mantener conversaciones con preguntas de seguimiento.
- Rechazar consultas ajenas al dominio antes de recuperar documentos.
- Conservar el parser determinista de metadatos como línea base explicable.
- Usar el LLM solo para revisar o corregir casos lingüísticos difíciles.
- Validar todas las salidas estructuradas antes de construir un filtro.
- Elegir una recuperación adecuada para cada tipo de pregunta.
- Mantener una traza persistente y serializable de cada turno.
- Generar respuestas limitadas a los registros recuperados.

## 2. Grafo actual

```text
START
  │
  ▼
PrepareTurn
  │
  ▼
RewriteQuery
  │
  ▼
Bouncer
  ├── NO GO ──────────────────────────────────────────────> END
  └── GO
       │
       ▼
DeterministicAnalysis
       │
       ▼
Reviewer
  ├── clarify ────────────────────────────────────────────> END
  ├── keep ────────────────────────────────┐
  └── extend / replace                     │
       │                                   │
       ▼                                   │
GenerateFilter                             │
       │                                   │
       ▼                                   │
ResolveWhere                               │
       └───────────────────────────────────┘
                         │
                         ▼
                  RetrievalMode
                     ├── hybrid  -> Retrieve ──────────┐
                     ├── min_max -> MinMaxRetrieve ───┤
                     └── count   -> CountRetrieve ────┤
                                                       ▼
                                                GenerateContext
                                                       │
                                                       ▼
                                                GenerateAnswer
                                                       │
                                                       ▼
                                                      END
```

La detección de `timeline` existe en `retrieval_mode.py`, pero todavía no tiene nodo ni arista de recuperación. No forma parte del flujo operativo actual.

## 3. Estado compartido

`GraphState` es un `TypedDict` con campos opcionales para que cada nodo escriba únicamente su resultado:

| Campo | Contenido |
|---|---|
| `messages` | Historial de usuario y asistente, con reductor aditivo |
| `user_query` | Última entrada literal del usuario |
| `query` | Consulta autónoma después de la reescritura |
| `decision` | `GO` o `NO GO` |
| `analysis` | Análisis determinista serializado |
| `review` | Revisión LLM serializada |
| `proposal` | Propuesta de filtros serializada, si existe |
| `deterministic_where` | Filtro producido por reglas |
| `final_where` | Filtro validado que recibe la recuperación |
| `retrieval_mode` | Plan serializado: híbrido, extremo o recuento |
| `raw_context` | `RetrievalResult` común |
| `context` | Texto preparado para el generador |
| `answer` | Respuesta final |

Los modelos Pydantic se convierten mediante `model_dump(mode="json")` antes de entrar en el estado. Los nodos que necesitan sus métodos los reconstruyen con `model_validate()`. Así los checkpoints no dependen de objetos Python complejos.

El modelo de embeddings, el cliente y la colección de Chroma, el catálogo y la conexión SQLite no forman parte del estado. Son recursos con ciclo de vida externo que `main_langgraph.py` carga una vez e inyecta mediante `functools.partial` al construir el grafo.

## 4. Preparación de la conversación

### `PrepareTurn`

`prepare_turn()` obtiene la última pregunta del historial, la guarda como `user_query` y limpia los campos técnicos que no deben arrastrarse desde el turno anterior. No borra `messages`.

### `RewriteQuery`

En el primer turno, `rewrite_query()` conserva una pregunta que ya es autónoma. Ante referencias como «allí», «ese día» o «¿y en Palencia?», utiliza Ollama para combinar la nueva entrada con el historial y producir una consulta independiente. El resto del grafo trabaja con `query`, no con la frase incompleta.

### Memoria

`main_langgraph.py` crea un `thread_id` por sesión y lo reutiliza en todas las llamadas a `graph.invoke()`. `SqliteSaver` guarda los estados en `data/checkpoints/langgraph.sqlite`. El historial puede inspeccionarse sin cargar BGE-M3 ni Chroma mediante `scripts/inspect_checkpoints.py`.

## 5. Admisión e interpretación

### `Bouncer`

`bouncer()` devuelve una decisión Pydantic binaria. `NO GO` genera una respuesta predeterminada, la añade al historial y termina. `GO` continúa. El prompt acepta referencias conversacionales reescritas y consultas implícitas propias del asistente, como pedir la última fecha registrada.

### `DeterministicAnalysis`

`build_deterministic_analysis(query, catalog)` se ejecuta una sola vez por turno. Conserva:

- `parsed_query`: consulta normalizada, `MetadataFilters` y ambigüedades;
- `deterministic_where`: diccionario compatible con Chroma o `None`;
- la última fecha del catálogo cuando resulta necesaria para interpretar el presente.

### `Reviewer`

El LLM compara la pregunta con el análisis y devuelve un `FilterReview`:

- `keep`: coherente y suficiente; copia `deterministic_where` a `final_where`;
- `extend`: debe añadir condiciones;
- `replace`: debe sustituir una interpretación incorrecta;
- `clarify`: no debe consultar hasta que el usuario aclare la intención.

### `GenerateFilter` y `ResolveWhere`

Solo se ejecutan para `extend` y `replace`. El LLM propone condiciones y grupos lógicos en un `FilterProposal`; nunca entrega un `where` libre para ejecutarlo directamente. El código valida los campos, operadores, tipos y valores canónicos, traduce la propuesta al formato de Chroma y resuelve el filtro final según la acción del revisor.

## 6. Selección y ejecución del retrieval

### `RetrievalMode`

`choose_retrieval_mode()` usa reglas reproducibles:

- preguntas descriptivas -> `hybrid`;
- primera, última, menor o mayor fecha -> `min_max`;
- cuántos incendios, snapshots o partes -> `count`;
- expresiones de evolución -> `timeline`, todavía sin ruta ejecutable.

### `Retrieve`

Genera un embedding normalizado de `query`, aplica `final_where` cuando existe y solicita a Chroma hasta diez resultados ordenados por similitud. Chroma filtra primero y ordena semánticamente dentro de las coincidencias.

### `MinMaxRetrieve`

Recibe la operación `min` o `max`. SQLite traduce el `where`, calcula la fecha extrema dentro de ese conjunto filtrado y devuelve todos los identificadores empatados en la fecha. Chroma recupera los documentos asociados por ID. Este orden garantiza que «último incendio de León» calcule el máximo de León y no la fecha global del corpus.

### `CountRetrieve`

SQLite devuelve un agregado exacto de incendios únicos, snapshots o informes. No se carga el modelo de embeddings ni se recuperan chunks. El valor cero se conserva como evidencia válida.

Los tres nodos producen `RetrievalResult`:

```python
{
    "mode": "hybrid | min_max | count",
    "ids": [],
    "documents": [],
    "metadatas": [],
    "distances": None,
    "aggregate": None,
}
```

Esto permite que las ramas converjan sin duplicar la lógica posterior.

## 7. Contexto y respuesta

`GenerateContext` transforma documentos o agregados en texto. `GenerateAnswer` envía a Ollama la pregunta autónoma, el contexto y el filtro aplicado. El prompt distingue:

- `WITH_DATA`: existen documentos o un agregado exacto, incluido cero;
- `NO_DATA`: no se recuperaron registros.

Una ausencia se formula como «no consta en los registros disponibles», no como prueba de que nunca haya existido un incendio. La respuesta del asistente se añade a `messages` para que pueda utilizarse en el turno siguiente.

## 8. Routing y terminación

Las funciones de routing leen datos simples del estado:

- `route_after_bouncer`: continúa solo con `GO`;
- `route_after_reviewer`: decide `generate`, `keep` o `end`;
- `route_after_retrieval_mode`: decide `hybrid`, `min_max` o `count`.

No existen ciclos automáticos ni llamadas ilimitadas a herramientas. Cada turno termina después de una sola recuperación y una sola generación, salvo las terminaciones anticipadas.

## 9. Pruebas y trazabilidad

Las pruebas del grafo sustituyen LLM, embeddings y almacenes por dobles. Comprueban las tres rutas operativas, la propagación de filtros, `NO GO`, `clarify`, `replace`, la convergencia en generación y la acumulación de mensajes durante varios turnos.

Los checkpoints conservan la evolución del estado. `scripts/inspect_checkpoints.py` permite revisar canales, pasos y valores sin abrir los recursos del RAG.

## 10. Trabajo pendiente

- Implementar el retrieval y routing de `timeline`.
- Añadir pruebas unitarias aisladas de los tres componentes LLM y de JSON inválido.
- Evaluar filtros, recuperación y respuesta con un conjunto estable de preguntas.
- Estudiar una evaluación de suficiencia del contexto y, solo si aporta valor medible, un único reintento controlado.
- Definir una política común de reintentos ante fallos transitorios de Ollama.
- Añadir trazas de evaluación separadas del historial conversacional si se necesitan métricas de producción.

## 11. Referencias

- [Arquitectura técnica general](ARQUITECTURA.md)
- [LangGraph: Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph: persistencia](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Ollama: Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)
