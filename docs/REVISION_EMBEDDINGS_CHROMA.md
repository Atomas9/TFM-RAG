# Revision de embeddings y ChromaDB

Fecha de revision: 2026-07-21.

Archivos revisados:

- `src/miteco_rag/embeddings_chroma.py`;
- `src/miteco_rag/chroma_tests.py`;
- `data/processed/fire_snapshots.jsonl`;
- coleccion local `MITECO_fire_snapshots` de `data/chroma`.

## Estado alcanzado

La primera version academica del indice vectorial esta operativa. El script
principal:

- construye rutas absolutas desde la ubicacion del propio archivo;
- carga cada linea del JSONL como un `FireSnapshot` validado por Pydantic;
- transforma los campos del snapshot en metadatos planos compatibles con
  Chroma;
- elimina de esos metadatos los valores `None`;
- usa `chunk_text` como documento y entrada del modelo;
- carga `BAAI/bge-m3` mediante Sentence Transformers en CPU;
- genera embeddings en lotes de ocho y los normaliza;
- abre una base persistente en `data/chroma`;
- obtiene o crea la coleccion `MITECO_fire_snapshots` sin funcion interna de
  embedding;
- inserta o actualiza los registros con `snapshot_id` como clave.

La proteccion `if __name__ == "__main__"` evita ejecutar la indexacion al
importar el modulo. La importacion relativa al archivo vecino esta pensada para
ejecutar directamente el script desde VS Code o desde la raiz del repositorio.

`chroma_tests.py` es una utilidad manual sencilla: abre la coleccion, muestra
el numero de registros y presenta tres documentos con sus metadatos. Su nombre
evita colisionar con el paquete `chromadb`. Como utiliza `Path("data/chroma")`,
debe ejecutarse desde la raiz del repositorio.

## Validacion realizada

Las comprobaciones se ejecutaron con el interprete del entorno Conda:

```text
/opt/anaconda3/envs/RAG-TFM/bin/python
```

Resultados:

- `pip check`: ninguna dependencia rota;
- los tres archivos Python compilan sin errores;
- 48 lineas del JSONL se reconstruyen como `FireSnapshot`;
- los 48 `snapshot_id` son unicos;
- Chroma contiene 48 registros;
- los conjuntos de IDs de Chroma y del JSONL coinciden;
- cada documento almacenado coincide con su `chunk_text`;
- se conservan 47 registros de Espana y uno de Portugal;
- cada embedding tiene 1.024 dimensiones;
- las normas minima y maxima observadas son 1, dentro de la precision numerica;
- los metadatos enviados a Chroma no contienen valores `None`;
- `data/processed` y `data/chroma` permanecen ignorados por Git.

El navegador de la CLI de Chroma no pudo cargar las filas aunque la API de
Python si abre y consulta correctamente la misma coleccion. Esto afecta a esa
herramienta de visualizacion, no a los datos almacenados. La utilidad
`chroma_tests.py` queda como forma reproducible de inspeccionarlos.

## Observaciones no bloqueantes

1. `upsert()` no borra un registro antiguo si su ID deja de aparecer en el
   JSONL. Habra que recrear la coleccion o sincronizar IDs al automatizar la
   ingesta.
2. La coleccion no registra todavia como metadatos propios el modelo, la
   dimension ni la version del indice.
3. `chroma_tests.py` depende del directorio desde el que se ejecuta y es una
   comprobacion manual, no una prueba pytest.
4. El parser emite un `SyntaxWarning` no bloqueante por escribir `\s` en una
   cadena explicativa que no es *raw string*.
5. El modulo usa una importacion vecina adecuada para la ejecucion directa,
   pero todavia no esta preparado como paquete instalable para ejecutarlo con
   `python -m miteco_rag.embeddings_chroma`.

## Siguiente incremento recomendado

1. Crear una funcion que genere el embedding normalizado de la pregunta con el
   mismo modelo.
2. Ejecutar una consulta semantica con `collection.query()`.
3. Incorporar filtros `where`, empezando por `country`, provincia y fecha.
4. Mostrar para cada resultado el texto, fecha, archivo y paginas de origen.
5. Convertir las comprobaciones actuales en pruebas automatizadas.
6. Conectar Ollama solo despues de validar la calidad de la recuperacion.
