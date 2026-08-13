# Extras del paquete

Esta carpeta conserva implementaciones educativas, históricas o de referencia
que no forman parte del flujo vigente ejecutado por `main_langgraph.py`.

## Contenido

- `fase1_parseo_miteco.py`: esqueleto inicial de la fase de parseo, mantenido
  como material histórico de aprendizaje.
- `retrieval_chroma_solution.py`: solución de referencia del retrieval híbrido.
  Sus pruebas se conservan en `tests/test_retrieval_chroma_solution.py`.
- `main_langgraph_inicial.py`: primera versión didáctica del grafo, anterior a
  la serialización segura, SQLite y los modos exactos de retrieval.
- `main_lineal_obsoleto.py`: antiguo punto de entrada lineal, conservado para
  comparar la evolución de la orquestación. No es ejecutable con los contratos
  actuales.

El parser operativo es `../parseo_y_chuncking.py`; el MVP utiliza
`../rag_graph.py`, `../retrieval_chroma.py` y `../main_langgraph.py`.
