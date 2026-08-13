# Utilidades del proyecto

Esta carpeta contiene comandos manuales de diagnóstico. No forman parte del
pipeline ni son módulos que importe `miteco_rag`.

- `inspect_chroma.py`: muestra las colecciones, el número de registros y una
  muestra de tres documentos de la colección local.
- `inspect_checkpoints.py`: recorre cronológicamente los checkpoints de una
  conversación a partir de su `thread_id`.

Se ejecutan desde la raíz del repositorio:

```bash
python scripts/inspect_chroma.py
python scripts/inspect_checkpoints.py
```

Ambas utilidades calculan sus rutas a partir de la ubicación del propio script.
No escriben datos ni cargan el modelo de embeddings.
