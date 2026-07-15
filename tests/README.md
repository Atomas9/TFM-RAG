# Pruebas

Las primeras pruebas automatizadas comprobaran:

- los recuentos actuales de 9, 9, 10 y 6 incendios en los cuatro PDF de
  referencia, con 34 snapshots en total;
- el numero de incendios extraidos de cada PDF de referencia;
- la conservacion de comunidad y provincia entre incendios consecutivos;
- la extraccion de fecha, estado, situacion operativa y pagina;
- la exclusion de registros que no correspondan a Espana;
- la ausencia del resumen estadistico dentro del ultimo chunk;
- la insercion y consulta de embeddings propios en ChromaDB;
- los filtros exactos por ubicacion, provincia, estado y fecha.
