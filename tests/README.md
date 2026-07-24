# Pruebas

Las pruebas previstas para el parser de PDF comprobaran:

- los recuentos actuales de 9, 9, 10, 6, 5, 4, 3 y 2 incendios en los ocho PDF
  de referencia, con 48 snapshots en total;
- el numero de incendios extraidos de cada PDF de referencia;
- la conservacion de comunidad y provincia entre incendios consecutivos;
- la extraccion de fecha, estado, situacion operativa y pagina;
- la extraccion de notas, fechas de inicio y medios asignados;
- la exclusion de registros que no correspondan a Espana;
- la ausencia del resumen estadistico dentro del ultimo chunk;
- la unicidad y estabilidad de los 48 `snapshot_id`;
- la agrupacion heuristica de ubicaciones repetidas mediante `incident_key`;
- el caso de Villablino, cuya fecha de inicio no aparece en todos los partes;
- que `incident_key` no se utiliza para eliminar snapshots;
- que `parse_miteco_pdf()` devuelve el recuento esperado de cada parte;
- que `parse_pdf_directory()` conserva los 48 snapshots y un orden
  determinista;
- que una carpeta vacia y un PDF inexistente generan `FileNotFoundError`;
- que importar el modulo no ejecuta el pipeline ni escribe archivos;
- que `validate_snapshots()` bloquea identificadores duplicados y contaminacion
  con el resumen estadistico;
- que `run_phase1()` genera 48 lineas JSONL validas y un `ParserReport`
  coherente;
- que fechas, tildes y modelos anidados sobreviven a la serializacion JSON;
- la insercion y consulta de embeddings propios en ChromaDB;
- que los IDs y documentos de Chroma coinciden con los del JSONL;
- que BGE-M3 genera un vector normalizado de 1.024 dimensiones por snapshot;
- que la conversion de metadatos elimina los valores `None` y conserva sus
  tipos simples;
- que una segunda ejecucion con los mismos snapshots no duplica registros;
- los filtros exactos por pais, ubicacion, provincia, estado y fecha;
- una consulta semantica y otra combinada con filtros.

## Pruebas implementadas

`test_query_filters.py` cubre el analizador sin depender del corpus local:

- inclusiones y exclusiones de provincias;
- `no de Leon sino de Palencia`;
- listas con `y` y `o` traducidas a `$in` o `$nin`;
- prioridad de `Castilla y Leon` frente a la provincia de Leon;
- reconocimiento de provincias validas ausentes del corpus, como Huelva;
- localizaciones dinamicas con articulo invertido;
- desambiguacion de provincia y comunidad de Madrid;
- paises, estados y situaciones operativas;
- fechas exactas, intervalos y comparaciones estrictas;
- consultas por mes y ano;
- presente implicito o explicito frente a formulaciones historicas;
- seleccion automatica del ultimo parte para consultas actuales;
- contradicciones y consultas sin filtros;
- la interfaz unificada `metadata_query(question, catalog)`.

`test_retrieval_chroma.py` usa dobles del modelo y de la coleccion para probar:

- el embedding normalizado enviado a Chroma;
- la presencia opcional de `where`;
- la devolucion auditable de `ParsedQuery` y del filtro final;
- el bloqueo de una consulta contradictoria antes de buscar.

`test_augmented_generator.py` usa un cliente Ollama simulado para comprobar:

- la numeracion y union de chunks;
- el contexto vacio;
- que no se llama al modelo sin documentos;
- que pregunta, contexto y modelo se envian correctamente.

La suite actual contiene 42 pruebas y se ejecuta con:

```bash
python -m pytest -q
```

Las pruebas del parser de PDF y una evaluacion de relevancia con preguntas y
resultados esperados siguen pendientes. Estas ultimas deberan separar calidad
semantica, exactitud de filtros y comportamiento cuando no existe respuesta.
