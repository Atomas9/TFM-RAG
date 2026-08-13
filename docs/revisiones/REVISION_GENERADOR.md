# Revisión del generador aumentado inicial

Fecha de revisión: 2026-07-24.

## Objetivo

Completar un primer MVP de extremo a extremo:

```text
pregunta
   ↓
retrieval híbrido en Chroma
   ↓
formateo de los chunks
   ↓
generación con Ollama Cloud
   ↓
respuesta fundamentada
```

Este MVP todavía no incorpora el revisor LLM de filtros ni LangGraph.

## Archivos

- `src/miteco_rag/augmented_generator.py`;
- `src/miteco_rag/extras/main_lineal_obsoleto.py` — ubicación actual del
  `main.py` lineal descrito en esta revisión histórica;
- `src/miteco_rag/retrieval_chroma.py`;
- `tests/test_augmented_generator.py`.

## Formateo del contexto

`retrieve()` devuelve un `QueryResult` de Chroma. Es una estructura semejante
a un diccionario con listas anidadas:

```python
{
    "ids": [["snapshot-1", "snapshot-2"]],
    "documents": [["chunk 1", "chunk 2"]],
    "metadatas": [[{...}, {...}]],
    "distances": [[0.1, 0.2]],
}
```

La lista exterior corresponde al lote de consultas. Como el proyecto envía una
sola pregunta, `documents[0]` contiene sus resultados.

`generate_context()` transforma esos documentos en un único string:

```text
[CHUNK 1]
...

---

[CHUNK 2]
...
```

Los chunks ya incluyen fecha, geografía, estado, archivo y página, por lo que
el primer MVP no vuelve a duplicar los metadatos dentro del prompt.

## Generación

`generate_answer()` recibe exclusivamente:

- pregunta;
- contexto ya formateado;
- nombre del modelo.

El system prompt obliga al modelo a:

- utilizar solo el contexto;
- reconocer información insuficiente;
- no completar con conocimiento externo;
- distinguir el último parte de la actualidad real;
- mencionar fecha, archivo y página;
- tratar los chunks como datos y no como instrucciones.

El modelo configurado es:

```text
gemma4:31b-cloud
```

Se comprobó mediante `ollama list` que está disponible en la instalación y se
realizó una llamada mínima satisfactoria a Ollama Cloud.

## Comportamiento sin documentos

Cuando Chroma devuelve `documents=[[]]`, el contexto es una cadena vacía y no
se llama al LLM. La respuesta controlada es:

> No se han recuperado registros con los filtros interpretados en esta
> consulta.

Esta redacción es deliberadamente prudente: un resultado vacío puede proceder
de una ausencia real o de una interpretación incorrecta de los filtros.

## Punto de entrada

El antiguo `main.py` solicitaba una pregunta por terminal y coordinaba:

```python
raw_context = retrieve(query=query, top_k=10)
context = generate_context(raw_context)
answer = generate_answer(query=query, context=context)
```

Puede ejecutarse desde la raíz mediante:

```bash
python src/miteco_rag/extras/main_lineal_obsoleto.py
```

Este comando documenta la ubicación histórica actual, pero el archivo ya no
es compatible con los contratos vigentes y no debe ejecutarse.

## Validación automatizada

Se añadieron cuatro pruebas sin llamadas reales a Cloud:

- unión y numeración de varios chunks;
- contexto vacío;
- ausencia de llamada a Ollama cuando no hay contexto;
- envío correcto de pregunta, contexto y modelo al cliente simulado.

La suite completa contiene 42 pruebas:

```text
42 passed
```

## Validación de extremo a extremo

Se ejecutó:

```text
¿Qué incendios estuvieron activos en León?
```

El retrieval recuperó cinco snapshots históricos y el modelo respondió
agrupando:

- Peranzanes;
- Villablino en los partes de los días 12, 13 y 14;
- Oseja de Sajambre, también identificado en la nota como Ribota de Sajambre.

La respuesta citó correctamente fechas, archivos y páginas.

## Limitación descubierta

La pregunta:

```text
¿Qué incendios ha habido en León y Andalucía?
```

generó:

```python
{
    "$and": [
        {"autonomous_community_normalized": "andalucia"},
        {"province_normalized": "leon"},
    ]
}
```

Esto exige que un mismo snapshot pertenezca simultáneamente a Andalucía y a la
provincia de León, por lo que devuelve cero resultados. La intención correcta
era un `$or` entre dos niveles geográficos.

La colección contiene:

- 5 snapshots de la provincia de León;
- 2 snapshots de Andalucía;
- 7 snapshots al aplicar el `$or`;
- 0 snapshots con el `$and` actual.

El modelo plano `MetadataFilters` puede representar listas dentro de un mismo
campo, pero no conserva todavía grupos lógicos entre campos diferentes. La
futura intención estructurada deberá representar condiciones geográficas con
su operador `AND` u `OR`.

No conviene convertir siempre geografías distintas en `$or`: `Villablino,
León` representa localización y provincia mediante `$and`. Esta decisión
requiere conservar la relación lingüística original y será revisada por el
nodo LLM acordado.

## Pendiente

El MVP es funcional y commiteable. Para la siguiente iteración quedan:

1. modelo Pydantic de intención y grupos lógicos;
2. nodo LLM de clasificación y revisión de filtros;
3. reconciliación determinista campo por campo;
4. evaluación del contexto antes de generar;
5. integración progresiva en LangGraph;
6. configuración externa del modelo y del cliente;
7. posibles citas estructuradas y streaming.
