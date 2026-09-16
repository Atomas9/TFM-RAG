# Pruebas automatizadas

La suite se ejecuta desde la raíz del repositorio:

```bash
python -m pytest -q
```

El estado validado el 16 de septiembre de 2026 contiene **137 pruebas**. La mayoría utiliza dobles para no descargar BGE-M3, llamar a Ollama Cloud ni depender de las bases locales.

## Cobertura actual

### Parser y snapshots

`test_parseo_y_chuncking.py` verifica:

- separación de incendios y conservación del contexto geográfico;
- extracción de fechas, estados, situación operativa, notas y medios;
- creación y estabilidad de `snapshot_id` e `incident_key`;
- serialización de modelos Pydantic;
- validaciones contra duplicados y contaminación del resumen estadístico;
- orden determinista y errores ante rutas inválidas;
- generación del JSONL y del informe del parser;
- tratamiento de partes que declaran cero actuaciones.

### Descarga automática

`test_download_miteco_report.py` cubre sin acceder a Internet:

- descubrimiento de enlaces y resolución de URL relativas;
- validación de firma, tipo MIME y fecha del PDF;
- escritura del documento y del manifiesto;
- idempotencia por SHA-256;
- revisiones y nombres históricos.

### Filtros y planificación

`test_query_filters.py` prueba inclusiones, exclusiones, grupos lógicos, geografía, estados, fechas, periodos, presente frente a pasado, contradicciones y la interfaz unificada del analizador.

`test_retrieval_mode.py` comprueba la selección de búsqueda híbrida, mínimo, máximo, recuentos y detección de consultas temporales.

### Persistencia e indexación

`test_embeddings_chroma.py` valida la firma de indexación, la selección de snapshots nuevos o modificados, la migración de registros antiguos y la salida sin cargar el modelo cuando no existen cambios.

`test_metadata_store.py` y `test_metadata_queries.py` verifican:

- creación e idempotencia de SQLite;
- índices para fechas, ubicaciones e incidentes;
- traducción parametrizada de filtros simples y grupos anidados;
- rechazo de campos, operadores y valores no permitidos;
- extremos globales o filtrados y todos sus empates;
- recuentos exactos, incluido cero.

### Recuperación y generación

`test_retrieval_chroma.py` prueba el contrato común `RetrievalResult`, la salida plana de Chroma, el cálculo del extremo después de filtrar y los recuentos sin embeddings.

`test_augmented_generator.py` cubre la construcción del contexto, documentos vacíos, agregados exactos y la distinción entre `WITH_DATA` y `NO_DATA` mediante un cliente Ollama simulado.

### Conversación y LangGraph

`test_prepare_turn.py` y `test_rewrite_query.py` comprueban la preparación del turno, la limpieza del estado técnico, la conservación del historial y la reescritura de preguntas dependientes.

`test_rag_graph.py` recorre con dependencias simuladas:

- ramas `hybrid`, `min_max` y `count`;
- propagación de filtros y parámetros de cada ruta;
- terminación anticipada para `NO GO` y `clarify`;
- generación y resolución de filtros LLM;
- convergencia en contexto y respuesta;
- acumulación ordenada de mensajes durante varios turnos.

`test_main_langgraph.py` valida el bucle de terminal, la carga única de recursos, la reutilización del `thread_id`, las entradas vacías y el cierre de Chroma y SQLite.

## Cobertura pendiente

- Contratos aislados de `bouncer.py`, `revisor_query_filters.py` y `generate_filter_LLM.py`, incluidas respuestas JSON inválidas.
- Rama de recuperación `timeline`, cuando se implemente.
- Evaluación de calidad con un conjunto estable de preguntas, resultados esperados y métricas separadas para filtros, recuperación y respuesta.
- Pruebas de integración opcionales contra Ollama Cloud y el corpus local completo.
