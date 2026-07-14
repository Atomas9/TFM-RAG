# Pruebas

Las primeras pruebas automatizadas comprobaran:

- el numero de incendios extraidos de cada PDF de referencia;
- la conservacion de comunidad y provincia entre incendios consecutivos;
- la extraccion de fecha, estado, situacion operativa y pagina;
- la exclusion de registros que no correspondan a Espana;
- la ausencia del resumen estadistico dentro del ultimo chunk;
- la insercion y consulta de embeddings propios en ChromaDB;
- los filtros exactos por ubicacion, provincia, estado y fecha.

