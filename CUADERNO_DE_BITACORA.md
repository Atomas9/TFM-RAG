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

## 2026-07-22

### Objetivo

Implementar una primera recuperacion hibrida que combine embeddings BGE-M3 con
filtros de metadatos interpretados de forma determinista.

### Trabajo realizado

- Se creo `src/miteco_rag/query_filters.py`.
- Se definieron `MetadataCatalog`, `MetadataFilters` y `ParsedQuery` como
  modelos Pydantic auditables.
- Se implemento la construccion del catalogo a partir de metadatos reales de
  Chroma.
- Se incorporaron catalogos completos de comunidades y provincias para
  reconocer lugares aunque no tengan registros en el corpus.
- Se mantuvieron las localizaciones como catalogo dinamico.
- Se implementaron inclusiones, exclusiones, coordinaciones y el contraste
  `no X sino Y`.
- Se implemento la prioridad de entidades compuestas, como `Castilla y Leon`,
  y la distincion entre provincia y comunidad de Madrid.
- Se incorporaron estados, situaciones operativas y fechas del parte exactas,
  por intervalos y mediante comparaciones.
- El catalogo conserva ahora todas las fechas disponibles y calcula
  `latest_report_date`.
- Se anadieron consultas por mes y ano, traducidas a intervalos sobre
  `report_date_number` sin duplicar metadatos en Chroma.
- Se distinguieron formulaciones historicas como `estuvieron activos` de las
  consultas de presente.
- Las expresiones `hay`, `existen`, `actualmente`, `ahora`, `hoy`, `a dia de
  hoy`, `en este momento` y `ultimo parte` seleccionan el ultimo parte cuando
  no existe una fecha explicita.
- Se implemento `build_chroma_where()` con operadores de igualdad, inclusion,
  exclusion, conjuncion y rango.
- Se anadio `metadata_query(question, catalog)` como interfaz unificada que
  devuelve directamente el valor de `where`.
- Se creo `retrieval_chroma_solution.py` como referencia para aceptar un
  `where` manual y ofrecer `retrieve_with_filters()` como recuperacion hibrida
  auditable.
- Se conservo `retrieval_chroma.py` con la version desarrollada por el alumno
  antes de esta solucion.
- En la solucion de referencia se elimino la consulta automatica durante la
  importacion mediante `main()`.
- Se crearon pruebas unitarias puras y pruebas de integracion con dobles.
- Se actualizaron README, arquitectura, pruebas y revision tecnica.

### Decisiones

- La interpretacion de la pregunta y la sintaxis de Chroma permanecen en
  funciones separadas.
- Las consultas ambiguas o contradictorias se detienen en lugar de elegir una
  interpretacion arbitraria.
- Las provincias ausentes, como Huelva o Palencia, producen un filtro valido y
  cero resultados; no se sustituyen por vecinos semanticos irrelevantes.
- La primera version es determinista y explicable. Un LLM para interpretar
  filtros se abordara en la siguiente sesion como alternativa experimental,
  con salida estructurada y validada antes de construir el `where`.
- Las fechas consultables son por ahora las fechas de los partes.
- El ultimo parte significa la fecha maxima del corpus y no equivale a una
  fuente de informacion en tiempo real.

### Validacion

- `python -m pytest -q`: 38 pruebas superadas.
- `query_filters.py`, `retrieval_chroma.py` y
  `retrieval_chroma_solution.py` compilan correctamente.
- `Hay incendios activos en Leon?` devuelve cero snapshots porque el ultimo
  parte global es del 19 de julio y no contiene activos de Leon.
- `Que incendios estuvieron activos en Leon?` devuelve los cinco snapshots
  historicos activos de esa provincia.
- `Que fuegos hay en Leon y Palencia?` genera un `$in` entre provincias y la
  fecha del ultimo parte; Palencia no contiene registros en el corpus.
- Palencia y Huelva se reconocen como provincias y devuelven cero registros.
- Castilla y Leon devuelve 9 snapshots de la comunidad.
- La exclusion de Espana devuelve el unico snapshot de Portugal.
- El intervalo del 12 al 15 de julio devuelve 30 snapshots dentro del rango.
- La situacion operativa 2 en Aragon devuelve 6 snapshots que cumplen ambos
  filtros.
- `git diff --check`: sin errores de formato.

### Problemas o riesgos

- El lenguaje determinista no pretende comprender cualquier construccion del
  espanol; solo las reglas documentadas y probadas.
- Las localizaciones que aun no existen en Chroma no pueden detectarse como
  filtros exactos.
- Todavia no hay evaluacion de relevancia ni umbral para rechazar vecinos
  semanticos debiles.
- No se ha implementado busqueda lexica ni fusion de rankings.
- La ruta automatica sigue usando similitud vectorial incluso para preguntas
  puramente estructuradas.

### Siguiente paso

Disenar una segunda version del analizador basada en un LLM que devuelva una
intencion estructurada. Compararla con la linea base determinista y conservar
la validacion Pydantic y la construccion controlada del filtro de Chroma.

## 2026-07-23

### Objetivo

Definir cómo se incorporará un LLM a la interpretación de consultas y crear
una explicación global del proyecto más cómoda de leer que la bitácora diaria.

### Trabajo realizado

- Se diseñó una arquitectura en la que el parser determinista y el parser LLM
  pueden ejecutarse y compararse de forma independiente.
- Se decidió que el LLM devolverá una intención estructurada validada con
  Pydantic, en lugar de escribir directamente el `where` de Chroma.
- Se propuso utilizar LangGraph cuando existan nodos ya comprobados para
  clasificación, retrieval, evaluación del contexto, reformulación y
  generación.
- Se acordó definitivamente utilizar LangGraph como workflow controlado con
  nodos deterministas y nodos asistidos por LLM.
- Se definió un nodo LLM que combina clasificación de dominio, revisión de los
  filtros deterministas y propuesta de correcciones.
- Se definió una reconciliación determinista campo por campo que conserva la
  procedencia de cada filtro.
- Se incorporó un planificador que podrá elegir retrieval semántico, híbrido,
  exhaustivo, recuento o línea temporal.
- Se añadió una evaluación posterior a Chroma que distingue contexto
  suficiente, cero coincidencias exactas, mala similitud y cobertura
  incompleta.
- Se limitó el futuro bucle de reformulación a un único segundo retrieval.
- Se creó `docs/PROCESO_DEL_PROYECTO.md`, que explica el desarrollo completo
  por etapas, las decisiones adoptadas, el estado actual y los límites.
- Se creó `docs/ARQUITECTURA_LANGGRAPH.md` con el grafo, sus ramas, el estado,
  los nodos, las reglas de validación y el orden previsto de implementación.
- Se enlazó la nueva guía desde el README.

### Decisiones

- El parser LLM se implementará primero como una función independiente.
- LangGraph se utilizará como workflow controlado, no como un agente con
  libertad para repetir consultas indefinidamente.
- El LLM propondrá una intención estructurada y nunca ejecutará directamente
  un `where` libre.
- Un error en un filtro no eliminará automáticamente todos los valores
  deterministas y una propuesta incompleta no se fusionará sin validación.
- Preguntas sobre todos los registros, recuentos o evoluciones no se resolverán
  siempre mediante `top_k`.
- Los resultados exactos vacíos se distinguirán de un contexto semántico de
  mala calidad.
- La versión determinista se conservará como línea base para evaluar la mejora
  real aportada por el LLM.

### Validación

- La nueva guía resume las fases desde la lectura de PDF hasta el retrieval
  híbrido y contiene los comandos para reconstruir el flujo.
- La arquitectura acordada queda documentada sin modificar el código.
- `git diff --check`: sin errores de formato.

### Siguiente paso

Definir los modelos Pydantic de intención y revisión e implementar el cliente
LLM como una función independiente. Después se probarán la reconciliación y los
nodos antes de montar el workflow completo.
