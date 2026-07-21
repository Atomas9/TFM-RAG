# Pruebas

Las primeras pruebas automatizadas comprobaran:

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

Durante la revision manual del 21 de julio se comprobaron los primeros cuatro
aspectos sobre los 48 registros actuales. Siguen pendientes de convertirse en
pruebas pytest para no depender del corpus local ni de volver a descargar el
modelo en cada ejecucion.
