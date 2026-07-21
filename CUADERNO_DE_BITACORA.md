# Cuaderno de bitacora

Registro cronologico del desarrollo del RAG de incendios forestales de MITECO.
Cada jornada debe anadir una entrada con los cambios realizados, las decisiones
adoptadas, las comprobaciones ejecutadas y los siguientes pasos.

## Plantilla de entrada

```markdown
## AAAA-MM-DD

### Objetivo

### Trabajo realizado

### Decisiones

### Validacion

### Problemas o riesgos

### Siguiente paso
```

## 2026-07-14

### Objetivo

Preparar el proyecto para desarrollar desde cero el parser y el RAG de los
partes diarios de MITECO.

### Trabajo realizado

- Se revisaron el downloader y el RAG manual existentes.
- Se inspeccionaron tres PDF reales de MITECO con 9, 9 y 10 incendios.
- Se detecto que algunos incendios consecutivos no repiten la provincia, por
  lo que el parser nuevo debera conservar comunidad y provincia como estado.
- Se definio una arquitectura con PyMuPDF, Pydantic, Sentence Transformers,
  BGE-M3, ChromaDB y Ollama Cloud.
- Se creo y valido el entorno Conda `RAG-TFM` con Python 3.11.
- Se corrigieron las incompatibilidades de NumPy, PyTorch y Transformers en
  macOS Intel.
- Se reorganizo el repositorio y se separo el material anterior en `extras`.
- Se creo `src/miteco_rag/fase1_parseo_miteco.py` como esqueleto tipado de la
  fase de parseo, sin implementar todavia el algoritmo.
- Se reviso el papel de las clases Pydantic como modelos de datos validados y
  se aclararon los conceptos de clase, instancia, atributo y serializacion.

### Decisiones

- Cada registro representara el estado de un incendio en un parte diario.
- Los filtros de ubicacion, fecha y estado se resolveran mediante metadatos.
- Chroma recibira embeddings calculados por el proyecto; no utilizara su
  modelo de embeddings predeterminado.
- Los PDF, resultados procesados e indices vectoriales no se versionaran.

### Validacion

- `python -m pip check`: sin dependencias rotas.
- Importacion conjunta de las dependencias: correcta.
- Lectura de un PDF con PyMuPDF: correcta.
- Insercion y consulta en Chroma con embeddings y filtro de ubicacion: correcta.

### Problemas o riesgos

- El equipo es macOS Intel y la ultima wheel compatible de PyTorch es la 2.2.2.
- Los cambios de formato de los PDF de MITECO requeriran pruebas con documentos
  de diferentes fechas.
- Uno de los registros revisados correspondia a Portugal y debera excluirse de
  la coleccion de Espana mediante una regla explicita.

### Siguiente paso

Retomar la fase 1 implementando y probando, en este orden:

1. `clean_line()`.
2. `normalize_for_match()`.
3. `calculate_sha256()`.
4. `extract_pdf_lines()` conservando el numero de pagina.

No se avanzara a la maquina de estados hasta poder inspeccionar y validar la
salida de estas cuatro funciones sobre un PDF real.

### Cierre de la jornada

La estructura del repositorio, el entorno `RAG-TFM` y el esqueleto de la fase 1
quedan preparados y validados. La sesion se cierra sin implementar todavia el
parser para continuar el 2026-07-15 desde las funciones basicas de
normalizacion y lectura del PDF.

## 2026-07-15

### Objetivo

Crear una solucion de referencia de la fase 1 en formato notebook y organizada
como apuntes ejecutables paso a paso.

### Trabajo realizado

- Se creo `notebooks/01_fase1_parseo_miteco.ipynb`.
- El notebook cubre lectura de PDF, normalizacion, metadatos documentales,
  maquina de estados, separacion por incendios, medios asignados, chunks,
  validacion y exportacion.
- Se anadieron pruebas para los 34 snapshots esperados y para los casos de
  provincias heredadas del parte del 13 de julio.
- Se incorporaron `ipykernel` y `nbformat` a las dependencias del proyecto.
- Se reviso `src/miteco_rag/parseo_y_chuncking.py` sin modificar el codigo del
  usuario.
- Se comprobo que la lectura, normalizacion, SHA-256 y extraccion de metadatos
  funcionan sobre los cuatro PDF disponibles.
- Se incorporo el parte del 14 de julio al recuento del corpus: 6 nuevas
  localizaciones y 34 en total.
- Se documento la revision en `docs/REVISION_FASE_1.md` y se actualizaron README,
  pruebas previstas y notebook de referencia.
- Se creó `docs/apuntes/LIBRERIAS.md` como guía de las dependencias y de los
  módulos de la biblioteca estándar empleados en el proyecto.

### Validacion de la implementacion del usuario

- Parte del 5 de julio: 161 lineas, 9 localizaciones.
- Parte del 12 de julio: 154 lineas, 9 localizaciones.
- Parte del 13 de julio: 156 lineas, 10 localizaciones.
- Parte del 14 de julio: 121 lineas, 6 localizaciones.
- Las cuatro fechas principales, las cuatro actualizaciones y los hashes se
  extrajeron correctamente.
- Se identifico como mejora previa al chunking evitar la ejecucion automatica
  del bloque de prueba cuando el modulo se importa.

### Siguiente paso

Anadir la proteccion `if __name__ == "__main__"`, controlar la carpeta sin PDF y
comenzar los catalogos geograficos antes de implementar la maquina de estados.

## 2026-07-19

### Objetivo

Revisar la ampliacion realizada en `parseo_y_chuncking.py` y actualizar la
documentacion con el estado real de la fase 1.

### Trabajo realizado

- Se revisaron los nuevos patrones de estado, fecha de inicio y medios.
- Se reviso el modelo Pydantic `AssignedResource`.
- Se comprobo la maquina de estados geografica y la separacion en `FireBlock`.
- Se revisaron los extractores de localizacion, estado, nota y medios
  asignados.
- Se incorporaron tres partes nuevos al inventario local: 15, 17 y 18 de julio.
- Se actualizaron README, `docs/REVISION_FASE_1.md` y `tests/README.md`.
- A peticion del usuario, se corrigieron las dos referencias a
  `line.clean_text` para usar `line.cleaned_text`.

### Decisiones

- Se mantiene la separacion en dos pasos: delimitacion del bloque y extraccion
  posterior de sus campos.
- La fecha del contenido del parte sera la autoridad para `report_date`; el
  nombre original se conservara como trazabilidad.
- No se avanzara a embeddings hasta disponer de registros completos validados
  y exportables a JSONL.

### Validacion

- `python -m py_compile src/miteco_rag/parseo_y_chuncking.py`: correcto.
- La demostracion incluida procesa el primer PDF y obtiene 9 bloques.
- El corpus contiene 7 PDF, 962 lineas utiles y 46 bloques candidatos.
- El parser corregido completa los siete PDF y obtiene 45 bloques de Espana y
  uno de Portugal sin errores.
- Los 46 bloques contienen un estado reconocible.
- El diagnostico produce 27 notas, 4 fechas de inicio completas y 135 objetos
  de medios, pendientes de contrastar manualmente con el PDF.

### Problemas o riesgos

- Las dos erratas `line.clean_text` quedaron corregidas durante la revision.
- La demostracion manual solo recorre tres bloques; por eso no sustituye a una
  prueba automatizada del corpus completo.
- El archivo `ActuacionesMITECO-definitivo15072025.pdf` contiene realmente el
  parte del 15 de julio de 2026.
- Todavia no hay pruebas pytest implementadas ni un modelo final que agrupe
  todos los campos del incendio.
- El campo `origin` de `AssignedResource` aun no se extrae.

### Siguiente paso

Crear pruebas automatizadas para los siete documentos. Despues se validaran
notas y medios contra una muestra real, se construira el modelo final del
incendio y se exportara el primer JSONL.

## 2026-07-20

### Objetivo

Integrar los campos extraidos en el modelo final `FireSnapshot` y preparar el
texto que se utilizara para generar embeddings.

### Trabajo realizado

- Se incorporo `PARSER_VERSION` para versionar la salida del parser.
- Se incorporo el modelo Pydantic `FireSnapshot`.
- Se implemento `short_sha256()` para identificadores deterministas.
- Se implemento `build_snapshot_id()` para identificar cada observacion dentro
  de su documento.
- Se implemento `build_incident_key()` como agrupacion heuristica de posibles
  observaciones del mismo incendio.
- Se implemento `build_chunk_text()` con fecha, geografia, localizacion,
  estado, medios, nota y fuente.
- Se implemento `build_fire_snapshot()` para coordinar todos los extractores.
- Se implemento `parse_miteco_pdf()` para orquestar todas las etapas de un
  documento.
- Se implemento `parse_pdf_directory()` para recorrer el corpus en orden
  determinista sin deduplicar snapshots diarios.
- Se implemento `validate_snapshots()` con comprobaciones de identificadores,
  paginas, geografia, medios y contaminacion del resumen.
- Se incorporo el modelo `ParserReport` y su resumen de archivos, paises,
  advertencias y errores.
- Se implementaron `write_snapshots_jsonl()` y `write_parser_report()`.
- Se implemento `run_phase1()` como orquestador de parseo, validacion y
  persistencia.
- Se elimino la ejecucion automatica durante los imports mediante `main()` e
  `if __name__ == "__main__"`.
- Se incorporo el parte del 19 de julio al corpus local.
- Se actualizaron README, arquitectura, revision tecnica y pruebas previstas.

### Decisiones

- `snapshot_id` identifica una observacion concreta y nunca se reutiliza para
  otro bloque.
- `incident_key` es una clave heuristica y no una identidad confirmada.
- Cuando falta la fecha de inicio, la clave agrupa por geografia y localizacion.
- Los snapshots no se eliminaran como duplicados por compartir `incident_key`.
- La resolucion definitiva de episodios se realizara posteriormente sobre el
  corpus ordenado por fecha.

### Validacion

- Los 8 PDF producen 1073 lineas y 48 snapshots: 47 de Espana y uno de
  Portugal.
- Los 48 `snapshot_id` son unicos.
- Se generan 37 `incident_key`; siete claves agrupan ubicaciones repetidas.
- Los 48 snapshots contienen estado y `chunk_text` no vacio.
- No hay rangos con `page_start` posterior a `page_end`.
- Se extraen 29 notas, 4 fechas de inicio completas y 157 medios candidatos.
- `python -m py_compile src/miteco_rag/parseo_y_chuncking.py`: correcto.
- Dos ejecuciones de `parse_pdf_directory()` devuelven los mismos 48 snapshots
  y conservan los 8 documentos.
- Una carpeta vacia y un PDF inexistente generan `FileNotFoundError` con un
  mensaje explicito.
- El archivo `fire_snapshots.jsonl` contiene 48 lineas JSON validas y
  reconstruibles como `FireSnapshot`.
- `parser_report.json` contiene los 8 documentos, 48 snapshots, cero
  advertencias y cero errores.
- La serializacion conserva fechas, modelos anidados, tildes y texto UTF-8.
- La importacion del modulo no procesa el corpus ni escribe archivos.
- Ambos artefactos generados estan ignorados por Git.

### Problemas o riesgos

- `incident_key` puede fusionar incendios distintos de una misma ubicacion si
  ninguno incluye fecha de inicio.
- Un mismo incendio puede dividirse si la fecha de inicio solo aparece en uno
  de sus partes; el corpus actual muestra este caso en Villablino.
- Los medios y notas aun deben contrastarse manualmente con los PDF.
- Todavia no existen pruebas pytest implementadas.
- La ejecucion actual reprocesa todos los PDF y sobrescribe las salidas; la
  indexacion incremental queda para una fase posterior.

### Siguiente paso

Continuar con la generacion de embeddings normalizados de `chunk_text` mediante
`BAAI/bge-m3` y almacenar vectores, documentos y metadatos planos en una
coleccion persistente de ChromaDB. La primera version reconstruira por completo
el indice.

## 2026-07-21

### Objetivo

Crear y validar la primera version minima del indice vectorial a partir de los
snapshots de la fase 1.

### Trabajo realizado

- Se creo `src/miteco_rag/embeddings_chroma.py`.
- Se implemento la lectura linea a linea de `fire_snapshots.jsonl` y la
  reconstruccion de cada registro como `FireSnapshot`.
- Se definio la conversion a metadatos planos compatibles con ChromaDB.
- Se genero un embedding normalizado de cada `chunk_text` mediante
  `BAAI/bge-m3`, Sentence Transformers, CPU y lotes de ocho.
- Se creo la coleccion persistente `MITECO_fire_snapshots` en `data/chroma`.
- Se almacenaron mediante `upsert` los IDs, embeddings, documentos y
  metadatos.
- Se mantuvo el snapshot de Portugal en la coleccion y se conservo `country`
  para poder filtrarlo en las consultas.
- Se renombro la utilidad de inspeccion a `chroma_tests.py` para evitar una
  colision de nombre con Chroma.
- Se actualizaron README, arquitectura, apuntes de librerias, pruebas previstas
  y la revision tecnica de esta fase.

### Decisiones

- La primera version prioriza un flujo pequeno y academico, sin LangChain ni
  LlamaIndex.
- El proyecto calcula los embeddings y Chroma se abre con
  `embedding_function=None`.
- `snapshot_id` es el ID del registro, `chunk_text` es el documento y los
  restantes campos consultables se guardan como metadatos.
- Se incluyen los 48 snapshots, tambien el de Portugal; las consultas
  restringidas a Espana usaran `country = "ES"`.
- La recuperacion y la generacion con Ollama quedan para la siguiente jornada.

### Validacion

- `pip check`: sin dependencias rotas en el entorno `RAG-TFM`.
- Los archivos del parser, el indexador y la utilidad de inspeccion compilan.
- El JSONL contiene 48 snapshots validos y con IDs unicos.
- Chroma contiene 48 registros: 47 de Espana y uno de Portugal.
- Los IDs y documentos almacenados coinciden con el JSONL.
- Cada vector tiene 1.024 dimensiones y norma unitaria.
- Los metadatos insertados no contienen valores `None`.
- Los datos procesados y el indice de Chroma siguen excluidos de Git.

### Problemas o riesgos

- La CLI `chroma browse` detecta la coleccion, pero falla al mostrar sus filas;
  la API de Python si las consulta correctamente.
- `upsert` inserta o actualiza, pero no elimina IDs obsoletos que hayan
  desaparecido del JSONL.
- La coleccion no guarda todavia la version del modelo ni del indice como
  metadatos propios.
- `chroma_tests.py` es una comprobacion manual y depende de ejecutarse desde la
  raiz del repositorio.
- Siguen pendientes las pruebas pytest.

### Siguiente paso

Implementar primero una consulta semantica sencilla con el mismo BGE-M3 y,
despues, filtros exactos de metadatos y consultas combinadas. La integracion con
Ollama se realizara cuando la recuperacion devuelva resultados pertinentes y
trazables.
