# Revisión del filtro LLM y del clasificador de entrada

## Objetivo

Esta fase añade dos controles al MVP:

1. corregir o completar filtros que el parser determinista no representa bien;
2. detener preguntas claramente ajenas a los partes de incendios forestales de
   MITECO.

## Propuesta estructurada de filtros

`generate_filter_LLM.py` recibe:

- la pregunta;
- el `DeterministicAnalysis`;
- el `FilterReview`;
- los valores canónicos del `MetadataCatalog`.

Solo se ejecuta cuando el revisor devuelve `extend` o `replace`. Ollama debe
responder con un `FilterProposal` compuesto por:

- `FilterCondition`: campo, operador y valor;
- `FilterGroup`: condiciones relacionadas mediante `and` u `or`;
- `FilterProposal`: grupos que se combinan entre sí mediante `AND`.

La propuesta representa el filtro completo. Esto evita combinar ciegamente el
filtro determinista con una corrección y conservar accidentalmente una
relación lógica errónea.

## Traducción determinista

El LLM no escribe directamente el `where`. Python traduce:

| Operador de la propuesta | Operador de Chroma |
| --- | --- |
| `eq` | igualdad directa |
| `ne` | `$ne` |
| `in` | `$in` |
| `nin` | `$nin` |
| `gte` | `$gte` |
| `lte` | `$lte` |

`condition_to_chroma()` valida cada condición. `group_to_chroma()` construye
un `$and` o `$or`, evitando operadores lógicos innecesarios cuando existe una
sola condición. `proposal_to_chroma_where()` combina los grupos y
`resolve_final_where()` selecciona el resultado final.

## Rutas del revisor

```text
keep
└── deterministic_where

extend / replace
└── FilterProposal → validación → final_where

clarify
└── mostrar problemas y terminar antes de Chroma
```

La consulta `¿Qué incendios ha habido en León y Andalucía?` fue revisada como
`replace`. El generador propuso un grupo OR entre provincia León y comunidad
Andalucía. El `where` resultante fue aceptado por Chroma y devolvió siete
registros.

## Bouncer

`bouncer.py` devuelve:

```python
class BouncerDecision(BaseModel):
    decision: Literal["GO", "NO GO"]
```

El clasificador solo decide si el pipeline continúa. No responde la pregunta,
no genera filtros y no comprueba si existen documentos.

El prompt fue reforzado para clasificar la intención principal. Una palabra
aislada como `fuego` no convierte una petición sobre la hora en una consulta
del dominio. Las preguntas mixtas reciben `GO` únicamente cuando contienen una
petición concreta sobre los partes o los incendios forestales.

## Structured outputs en Ollama Cloud

El código envía el esquema Pydantic mediante:

```python
format=BouncerDecision.model_json_schema()
```

Ollama Cloud no soporta actualmente structured outputs, por lo que el modelo
puede devolver `NO GO` como texto plano en vez de:

```json
{"decision": "NO GO"}
```

El prompt muestra el formato obligatorio y Pydantic mantiene la validación
estricta. Queda pendiente decidir si se realizará un reintento o una
normalización limitada a las etiquetas exactas.

## Validación realizada

- Los módulos nuevos y modificados compilan.
- `bouncer`, `generate_filter_LLM` y `main` se importan correctamente.
- La suite completa mantiene 53 pruebas superadas.
- El filtro OR de León y Andalucía fue ejecutado contra la colección real.
- Las fechas inválidas y combinaciones incompatibles de operador y valor se
  rechazan antes de consultar Chroma.

## Pendientes

- Añadir pruebas simuladas del bouncer para `GO`, `NO GO`, JSON inválido,
  palabra clave aislada e instrucciones adversarias.
- Añadir pruebas del generador y del traductor para operadores, grupos, fechas
  y las cuatro acciones del revisor.
- Validar valores canónicos contra el catálogo.
- Detectar condiciones duplicadas o contradictorias.
- Definir la política de recuperación ante salidas no JSON de Ollama Cloud.
- Cargar el modelo de embeddings y Chroma después de que el bouncer devuelva
  `GO`.
- Eliminar el bloque de depuración comentado de `main.py`.
