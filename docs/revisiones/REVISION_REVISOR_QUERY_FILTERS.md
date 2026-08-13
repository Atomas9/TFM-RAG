# Revisión inicial del revisor LLM de filtros

## Objetivo

`src/miteco_rag/revisor_query_filters.py` compara la pregunta del usuario con
el análisis producido por el parser determinista. Su responsabilidad termina
en decidir si los filtros son coherentes y suficientes; no consulta documentos,
no responde la pregunta y no genera todavía un nuevo `where`.

## Entrada

La función `revisor()` recibe:

- la pregunta del usuario;
- un `DeterministicAnalysis` ya construido para esa pregunta.

El análisis contiene el `ParsedQuery`, sus filtros estructurados, las
ambigüedades y el `deterministic_where`. El revisor ya no abre Chroma, no
reconstruye el catálogo y no vuelve a ejecutar el parser. Esta separación
permite calcular una sola vez la interpretación determinista y reutilizarla en
las fases posteriores.

El análisis se serializa como JSON legible mediante `json.dumps()`. Se utiliza
`ensure_ascii=False` para conservar tildes y `indent=2` para facilitar la
inspección durante el desarrollo.

## Salida

Ollama debe responder conforme a `FilterReview`:

```python
class FilterReview(BaseModel):
    action: Literal["keep", "extend", "replace", "clarify"]
    coherent: bool
    sufficient: bool
    issues: list[str]
    explanation: str
```

Las acciones significan:

- `keep`: el análisis es correcto y completo;
- `extend`: es correcto, pero faltan condiciones;
- `replace`: existe una interpretación o relación lógica incorrecta;
- `clarify`: la intención no puede determinarse con seguridad.

`coherent` y `sufficient` son dimensiones independientes. Un análisis puede
contener todas las entidades solicitadas y ser suficiente, pero relacionarlas
incorrectamente y no ser coherente.

La llamada utiliza el esquema JSON de Pydantic, temperatura cero y
`model_validate_json()` para obtener un objeto validado.

## Validación manual realizada

Se ejecutaron cuatro llamadas reales con `gemma4:31b-cloud`:

| Pregunta | Acción | Resultado |
| --- | --- | --- |
| ¿Qué incendios activos hay en León? | `keep` | Provincia, estado y último parte reconocidos |
| ¿Qué incendios ha habido en León y Andalucía? | `replace` | Detectó el `AND` geográfico incorrecto y propuso conceptualmente `OR` |
| Incendios de León, pero no de León | `clarify` | Detectó la contradicción |
| ¿Qué medios aéreos han participado en los incendios? | `keep` | Consideró correcto `where=null` para una consulta semántica |

También se comprobó que una pregunta vacía produce `ValueError` antes de
realizar la llamada al modelo.

## Pruebas pendientes

Las comprobaciones manuales no sustituyen a las pruebas automatizadas. Queda
pendiente crear `tests/test_revisor_query_filters.py` con una colección y un
cliente Ollama simulados para comprobar:

- las respuestas `keep`, `extend`, `replace` y `clarify`;
- una respuesta JSON inválida o incompatible con `FilterReview`;
- una pregunta vacía sin llamada al modelo;
- el contenido del análisis determinista enviado en el prompt.

Estas pruebas verificarán el contrato Python sin depender de la red ni consumir
llamadas Cloud. Un conjunto separado de evaluación real medirá la calidad del
prompt y de las decisiones del modelo.

## Siguientes componentes

1. Definir una intención estructurada que represente grupos `AND/OR`.
2. Crear el LLM que proponga filtros cuando la acción sea `extend` o `replace`.
3. Validar campos, operadores, valores y fechas con código determinista.
4. Reconciliar la propuesta con los filtros originales.
5. Crear el clasificador que decida si la pregunta pertenece al dominio de
   incendios de MITECO.
6. Integrar los componentes ya probados como nodos de LangGraph.

El LLM corrector no escribirá directamente un diccionario libre de Chroma. Su
propuesta será validada con Pydantic y traducida deterministicamente al
`where` final.

## Refactorización de recursos

`core.loader()` centraliza la carga del modelo `BAAI/bge-m3`, la colección
persistente de Chroma y el `MetadataCatalog`. `main.py` construye después:

```python
analysis = build_deterministic_analysis(query, catalog)
review = revisor(query, analysis)
```

El resultado del revisor todavía no gobierna el retrieval. Mientras no se
complete el generador y la reconciliación, Chroma utiliza
`analysis.deterministic_where`.
