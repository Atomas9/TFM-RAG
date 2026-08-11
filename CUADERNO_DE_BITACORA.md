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

## 2026-07-24

### Objetivo

Completar y validar un MVP que conecte el retrieval híbrido con un LLM
generador de respuestas mediante Ollama Cloud.

### Trabajo realizado

- Se terminó `generate_context()` para convertir el `QueryResult` anidado de
  Chroma en un único texto con chunks numerados.
- Se completó `generate_answer()` con mensajes `system` y `user`, grounding,
  referencias documentales y respuesta controlada para contexto vacío.
- Se creó `src/miteco_rag/main.py` como punto de entrada interactivo.
- Se confirmó que `gemma4:31b-cloud` está disponible en Ollama.
- Se añadieron cuatro pruebas unitarias con un cliente Ollama simulado.
- Se detectó una limitación del filtro plano al coordinar León, provincia, con
  Andalucía, comunidad autónoma: actualmente se genera un `$and` imposible en
  lugar del `$or` pretendido.
- Se creó `docs/REVISION_GENERADOR.md` y se actualizaron README, arquitectura,
  proceso y documentación de pruebas.

### Decisiones

- El contexto se construye como un string, aunque durante su preparación se
  utilice una lista de fragmentos.
- Las instrucciones permanentes permanecen en el mensaje `system` y la
  pregunta y el contexto se envían en el mensaje `user`.
- Un contexto vacío no activa una llamada al LLM.
- La respuesta sin documentos no afirma que el incendio no existiera; indica
  que no se recuperaron registros con los filtros interpretados.
- Los futuros filtros estructurados deberán conservar grupos lógicos `AND/OR`
  entre entidades de distintos niveles geográficos.

### Validación

- `python -m pytest -q`: 42 pruebas superadas.
- `augmented_generator.py` y `main.py` compilan correctamente.
- `git diff --check`: sin errores de formato.
- La llamada mínima a `gemma4:31b-cloud` respondió correctamente.
- La prueba completa `¿Qué incendios estuvieron activos en León?` recuperó
  cinco snapshots y produjo una respuesta que agrupó incendios y citó fechas,
  archivos y páginas.
- La colección contiene 5 snapshots de León y 2 de Andalucía; el `$or`
  correcto devolvería 7, mientras el `$and` actual devuelve 0.

### Problemas o riesgos

- El parser determinista no conserva todavía la relación lógica entre
  geografías de campos diferentes.
- El generador confía en el contexto recuperado porque todavía no existe un
  nodo separado de evaluación de suficiencia.
- El modelo y el acceso a Ollama todavía están configurados en el código y no
  mediante una configuración externa.
- No se han implementado streaming ni citas estructuradas.

### Siguiente paso

Definir el modelo Pydantic de intención con grupos lógicos y construir el
revisor LLM que clasifique el dominio y evalúe la coherencia y suficiencia de
los filtros deterministas.

## 2026-07-25

### Objetivo

Automatizar la descarga del parte definitivo diario de MITECO para no depender
de una descarga manual durante periodos de ausencia.

### Trabajo realizado

- Se creó `src/miteco_rag/download_miteco_report.py` como módulo independiente,
  sin modificar los scripts del parser, embeddings, retrieval o generación.
- El descargador descubre el enlace desde la página oficial en vez de fijar
  directamente la URL del PDF.
- Se añadió validación de firma, MIME, apertura con PyMuPDF, encabezado real y
  fecha escrita en la primera página.
- Se exige que el documento corresponda al día anterior según
  `Europe/Madrid`; un enlace todavía desactualizado provoca un error visible.
- Se implementó deduplicación por SHA-256, detección de revisiones y
  compatibilidad con los nombres históricos ya existentes.
- Se incorporó `manifest.jsonl` con procedencia, fecha, tamaño, hash y relación
  con una versión previa.
- Se creó `.github/workflows/download-miteco-report.yml` con ejecuciones a las
  12:37 y 18:17, ejecución manual y commits mediante `github-actions[bot]`.
- Se modificó `.gitignore` únicamente para versionar `data/raw/miteco`; los
  datos procesados y Chroma continúan excluidos.
- Se añadieron 11 pruebas unitarias sin red.
- Se creó `docs/INGESTA_AUTOMATICA_MITECO.md` y se actualizaron README,
  arquitectura, proceso, datos y documentación de pruebas.
- Se limpió el paquete principal moviendo el esqueleto educativo de fase 1 y
  la solución de referencia del retrieval a `src/miteco_rag/extras/`.
- La prueba de la solución de referencia se renombró a
  `tests/test_retrieval_chroma_solution.py` y conserva sus cuatro casos.

### Decisiones

- Los PDF se guardarán inicialmente mediante commits normales del repositorio.
- El workflow solo captura el documento fuente; no ejecuta todavía el parser,
  los embeddings ni la actualización de Chroma.
- Dos intentos diarios aportan tolerancia a publicaciones tardías y fallos
  transitorios sin generar duplicados.
- Los documentos nuevos usan una fecha ISO en el nombre. Los nombres antiguos
  no se renombran para preservar las referencias existentes.
- Si MITECO revisa un parte, se reemplaza el archivo de trabajo y Git conserva
  la versión anterior en su historial.

### Validación

- 11 pruebas específicas del descargador superadas.
- Descarga real validada contra MITECO en una carpeta temporal.
- El documento detectado corresponde al 24 de julio de 2026 y su SHA-256 es
  `f853390fb2103eb631679a5eb4bdf083b597cf3bf99ab683df05afa4dde37ca6`.

### Siguiente paso

Activar y observar el workflow en GitHub. Después se retomará el revisor LLM de
los filtros deterministas; la conexión entre la descarga automática y el
reprocesado del índice se decidirá en una fase posterior.

## 2026-07-25 — Revisor LLM de filtros

### Objetivo

Crear y comprobar como función independiente el LLM encargado de revisar si el
análisis determinista de una pregunta es coherente y suficiente.

### Trabajo realizado

- Se creó `src/miteco_rag/revisor_query_filters.py`.
- Se definió `FilterReview` con las acciones `keep`, `extend`, `replace` y
  `clarify`.
- El revisor utiliza `parse_metadata_filters()` para conservar filtros y
  ambigüedades antes de construir el `where`.
- El análisis determinista se serializa como JSON legible y se incorpora al
  prompt junto con la pregunta.
- Se redactó un system prompt que limita el nodo a revisar los filtros y
  distingue búsquedas estructuradas de preguntas puramente semánticas.
- Ollama recibe el JSON Schema de Pydantic, temperatura cero y la respuesta se
  valida mediante `FilterReview.model_validate_json()`.
- Se aclaró que `coherent` y `sufficient` son dimensiones independientes: un
  filtro puede contener todas las entidades y relacionarlas incorrectamente.

### Validación real

Se realizaron cuatro llamadas con `gemma4:31b-cloud`:

- `¿Qué incendios activos hay en León?` devolvió `keep`.
- `¿Qué incendios ha habido en León y Andalucía?` devolvió `replace` y detectó
  correctamente el `AND` imposible frente al `OR` solicitado.
- `Incendios de León, pero no de León` devolvió `clarify`.
- `¿Qué medios aéreos han participado en los incendios?` devolvió `keep` y
  consideró correcto no utilizar filtros de metadatos.

Una pregunta vacía produjo el `ValueError` esperado antes de llamar al modelo.
El archivo compila correctamente.

### Decisiones

- El revisor no clasificará el dominio ni generará directamente un nuevo
  `where`.
- El clasificador de preguntas y el generador LLM de filtros se implementarán
  como componentes independientes.
- El corrector devolverá una intención Pydantic con grupos lógicos; Python
  validará y traducirá la propuesta a Chroma.
- LangGraph se incorporará cuando estas funciones se hayan probado de manera
  aislada.

### Pendiente

- Crear `tests/test_revisor_query_filters.py` con Chroma y Ollama simulados.
- Cubrir `keep`, `extend`, `replace`, `clarify`, JSON inválido y pregunta vacía.
- Mantener aparte un conjunto de evaluación con llamadas reales para medir la
  calidad del prompt.
- Definir el esquema de intención con condiciones y grupos `AND/OR`.
- Implementar el LLM que proponga filtros para `extend` y `replace`.
- Implementar la validación, reconciliación y traducción deterministas.
- Crear el decisor que clasifique si la pregunta pertenece al dominio de
  incendios de MITECO.
- Normalizar los imports internos antes de construir los nodos de LangGraph.

### Próxima sesión

Continuar con el generador LLM de filtros y el clasificador de dominio. Las
pruebas automatizadas del revisor quedan registradas como deuda inmediata antes
de integrar el grafo completo.

## 2026-07-27 — Refactorización del flujo de consulta

### Objetivo

Evitar que el modelo de embeddings, Chroma, el catálogo y el análisis
determinista se carguen o calculen repetidamente en cada componente.

### Trabajo realizado

- Se creó `src/miteco_rag/core.py`.
- `core.loader()` carga una sola vez `BAAI/bge-m3`, la colección
  `MITECO_fire_snapshots` y el `MetadataCatalog`.
- Se añadió `DeterministicAnalysis` para agrupar el `ParsedQuery` y el
  `deterministic_where`.
- Se añadió `build_deterministic_analysis(query, catalog)` para interpretar
  cada pregunta una sola vez.
- `revisor_query_filters.py` dejó de abrir Chroma, reconstruir el catálogo y
  repetir el análisis determinista.
- `retrieval_chroma.py` dejó de cargar recursos internamente y ahora recibe el
  modelo, la colección y el `where`.
- `main.py` pasó a actuar como orquestador del flujo refactorizado.
- Se definieron tipos de retorno y parámetros para `loader()` y `retrieve()`.
- Se verificó el retrieval con dobles de modelo y colección y el flujo de
  `main.py` con dependencias simuladas.

### Validación

- Los módulos refactorizados compilan correctamente.
- La suite completa supera 53 pruebas.
- La prueba integrada simulada recorrió carga, análisis, revisión, retrieval,
  construcción de contexto y generación de respuesta.
- `core.py`, `query_filters.py`, `revisor_query_filters.py`,
  `retrieval_chroma.py`, `augmented_generator.py` y `main.py` se importan
  correctamente.

### Estado del generador de filtros

`src/miteco_rag/generate_filter_LLM.py` está a medio implementar. Ya contiene
los modelos iniciales `FilterCondition`, `FilterGroup` y `FilterProposal`, pero
faltan:

- adaptar su entrada para reutilizar `DeterministicAnalysis`;
- eliminar imports anteriores a la refactorización;
- redactar los prompts;
- serializar la pregunta, el análisis, la revisión y el catálogo necesario;
- validar y traducir la propuesta antes de usarla como filtro;
- conectar las rutas `extend` y `replace`.

Actualmente el archivo conserva un import de `load_chroma_collection` desde
`retrieval_chroma.py`, función que ahora reside en `core.py`. Como el generador
no debe consultar Chroma directamente, ese import deberá eliminarse.

### Decisiones

- El revisor recibe el análisis ya calculado y no conoce cómo se cargaron los
  recursos.
- El retrieval recibe todas sus dependencias y se limita a generar el
  embedding de la pregunta y consultar Chroma.
- `deterministic_where` se conserva como nombre para distinguirlo del futuro
  `llm_where` o `final_where`.
- La trazabilidad del pipeline es conveniente, pero se aplaza hasta completar
  el generador de filtros.
- El futuro historial de conversación se guardará en `messages`; las trazas
  técnicas se mantendrán separadas y no se enviarán al LLM de respuesta.

### Pendiente para la próxima sesión

1. Terminar `generate_filter_LLM.py`.
2. Definir su contrato con `DeterministicAnalysis`, `FilterReview` y catálogo.
3. Eliminar imports obsoletos y comprobar que el módulo se puede importar.
4. Construir el prompt y validar la salida `FilterProposal`.
5. Diseñar la traducción y reconciliación determinista del filtro propuesto.
6. Hacer que `review.action` gobierne las rutas `keep`, `extend`, `replace` y
   `clarify`.

La trazabilidad estructurada y el clasificador de dominio quedan para sesiones
posteriores.

## 2026-07-29 — Filtro final LLM y bouncer

### Objetivo

Completar la corrección de filtros para `extend` y `replace` y añadir una
primera barrera que impida ejecutar el RAG con preguntas ajenas al dominio.

### Trabajo realizado

- Se completó el prompt de `generate_filter_LLM.py`.
- El generador recibe la pregunta, `DeterministicAnalysis`, `FilterReview` y
  valores canónicos del catálogo.
- Se definió `FilterProposal` mediante condiciones y grupos lógicos.
- Se añadieron `condition_to_chroma()`, `group_to_chroma()` y
  `proposal_to_chroma_where()`.
- Se añadió `resolve_final_where()` para conservar el filtro determinista en
  `keep` y utilizar la propuesta completa en `extend` y `replace`.
- Se validan operadores escalares y de lista, listas vacías, rangos y fechas
  reales de ocho cifras `YYYYMMDD`.
- `main.py` utiliza el nuevo filtro antes del retrieval.
- La ruta `clarify` muestra los problemas y termina el flujo.
- Se creó `bouncer.py` con una decisión Pydantic binaria `GO`/`NO GO`.
- El bouncer se conectó antes del análisis determinista.
- El prompt del bouncer se corrigió para exigir objetos JSON y clasificar la
  intención, no palabras clave aisladas.

### Pruebas y resultados

- El revisor clasificó `¿Qué incendios ha habido en León y Andalucía?` como
  `replace`.
- El generador propuso un OR entre provincia León y comunidad Andalucía.
- El traductor produjo un `where` válido que Chroma aceptó y que devolvió siete
  snapshots.
- Se comprobaron condiciones con uno y varios grupos, `keep`, `replace`,
  `clarify`, operadores incompatibles y fechas inválidas.
- Los módulos compilan y se importan correctamente.
- La suite completa mantiene 53 pruebas superadas.

### Incidencias

- Ollama Cloud devolvió inicialmente `NO GO` como texto plano aunque se había
  enviado un JSON Schema mediante `format`.
- La documentación oficial indica que Ollama Cloud no soporta actualmente
  structured outputs.
- Se corrigieron todos los ejemplos del prompt para mostrar
  `{"decision": "GO"}` o `{"decision": "NO GO"}`.
- La consulta `¿Qué hora es? Fuego` superó inicialmente el clasificador porque
  el prompt daba demasiado peso a la palabra `fuego`. Se añadieron reglas y
  ejemplos para evaluar la intención principal y rechazar palabras aisladas.

### Decisiones

- El LLM propone una intención estructurada, pero Python construye el `where`.
- La propuesta de `extend` y `replace` representa el filtro completo; no se
  combina a ciegas con el filtro determinista.
- Se conserva `format` para compatibilidad con backends que sí soportan
  structured outputs y Pydantic valida siempre la respuesta.
- La primera versión del bouncer será binaria. Una taxonomía más detallada
  podrá incorporarse con LangGraph si la evaluación demuestra que hace falta.

### Pendiente para la próxima sesión

1. Crear pruebas automatizadas del bouncer, revisor, generador y traductor.
2. Definir una recuperación controlada ante JSON inválido o texto plano de
   Ollama Cloud.
3. Validar valores del LLM contra el catálogo y detectar contradicciones.
4. Mover `loader()` después del `GO` para no cargar BGE-M3 y Chroma en
   preguntas rechazadas.
5. Limpiar el bloque de depuración comentado de `main.py`.
6. Comenzar la integración con LangGraph cuando los contratos estén cubiertos
   por pruebas.

Se mantiene aplazada la trazabilidad estructurada del pipeline.

## 2026-08-03 — Primera orquestación funcional con LangGraph

### Objetivo

Reproducir el pipeline de consulta existente mediante un grafo de estados sin
reescribir las funciones ya desarrolladas y manteniendo un ejemplo sencillo y
académico.

### Trabajo realizado

- Se añadió `langgraph` a las dependencias del entorno `RAG-TFM`.
- Se creó `src/miteco_rag/rag_graph.py` con un `GraphState` compartido.
- Se mantuvieron los nodos fuera de `create_graph()` para separar su lógica de
  la construcción del workflow.
- `loader()` se ejecuta una sola vez al construir el grafo; el modelo de
  embeddings, la colección de Chroma y el catálogo no se guardan en el estado.
- Los nodos que requieren recursos externos los reciben mediante
  `functools.partial`.
- Se implementaron los nodos `Bouncer`, `DeterministicAnalysis`, `Reviewer`,
  `GenerateFilter`, `ResolveWhere`, `Retrieve`, `GenerateContext` y
  `GenerateAnswer`.
- Se añadieron rutas condicionales para detener `NO GO` y `clarify`, conservar
  el filtro determinista en `keep` y generar un filtro nuevo en `extend` o
  `replace`.
- El estado conserva `deterministic_where` y `final_where` por separado para
  comparar la interpretación inicial con el filtro realmente aplicado.
- Se creó `src/miteco_rag/main_langgraph.py` como punto de entrada mínimo por
  terminal.
- Se incorporó `MemorySaver` con un `thread_id` para disponer de checkpoints
  durante la vida del proceso.

### Validación

- `rag_graph.py` y `main_langgraph.py` compilan correctamente.
- LangGraph construye el grafo y reconoce todos los nodos registrados.
- Con Ollama, Chroma y embeddings simulados se comprobaron las rutas `NO GO`,
  `keep`, `replace` y `clarify`.
- `keep` aplica el filtro determinista y `replace` aplica el filtro generado.
- La suite completa continúa superando 53 pruebas; permanecen únicamente cinco
  advertencias externas de SWIG.
- No se realizó en este cierre una prueba completa adicional contra Ollama
  Cloud.

### Decisiones

- LangGraph orquesta funciones independientes; la lógica de dominio no se
  reimplementa dentro del framework.
- Los recursos pesados son dependencias del grafo, no datos del estado ni de
  los checkpoints.
- `partial` deja configurados los argumentos externos y permite que LangGraph
  invoque cada nodo proporcionando solamente el estado.
- La ruta `keep` pasa directamente de `Reviewer` a `Retrieve`; no ejecuta
  `ResolveWhere` porque el revisor ya establece `final_where`.
- El historial conversacional no se mezclará con las decisiones técnicas del
  pipeline.

### Próxima sesión

1. Permitir varias preguntas en la misma ejecución.
2. Diseñar y guardar el historial de mensajes de la conversación.
3. Resolver preguntas dependientes del contexto, como `¿Y en Palencia?`, antes
   de ejecutar el análisis determinista.
4. Evitar que resultados transitorios de una pregunta anterior contaminen la
   siguiente ejecución del mismo hilo.
5. Guardar una traza persistente por consulta y sustituir posteriormente
   `MemorySaver` por un checkpointer local duradero.
6. Añadir pruebas automatizadas específicas de los nodos y rutas del grafo.

## 2026-08-10 — Persistencia SQLite y revisión de la traza

### Trabajo realizado

- Se instaló `langgraph-checkpoint-sqlite` en el entorno `RAG-TFM` y se añadió
  a `requirements.txt`.
- `main_langgraph.py` pasó a crear un `SqliteSaver` y a proporcionar el
  checkpointer a `create_graph()`.
- Los checkpoints se guardan en `data/checkpoints/langgraph.sqlite` y se
  agrupan por `thread_id`.
- La base SQLite se excluyó de Git y `data/checkpoints/.gitkeep` conserva el
  directorio vacío en el repositorio.
- Se creó `inspect_checkpoints.py` para consultar una conversación mediante su
  identificador y recorrer `graph.get_state_history(config)`.
- Se comprobó una ejecución real con ocho checkpoints desde la entrada hasta
  `GenerateAnswer`.

### Hallazgos

- LangGraph puede guardar los modelos Pydantic actuales, pero advierte que está
  deserializando tipos personalizados no registrados. Una versión futura puede
  bloquear este comportamiento.
- `inspect_checkpoints.py` llama a `create_graph()` y, por tanto, carga BGE-M3,
  Chroma y el catálogo aunque la inspección solo necesite SQLite.
- La pregunta `¿Cuál es la última fecha de incendios que tienes registrada?`
  produjo correctamente `where=None`: no contiene una condición que limite el
  conjunto de documentos.
- El revisor devolvió `keep` correctamente dentro de su contrato, ya que solo
  evalúa filtros de metadatos.
- El pipeline aplicó después ranking semántico y respondió con la fecha máxima
  de los diez chunks recuperados, no con la fecha máxima de toda la colección.
  Esto demostró que falta seleccionar el modo de consulta antes del retrieval.

### Tareas pendientes y prioridad

1. Serializar de forma explícita los modelos Pydantic de `GraphState` mediante
   estructuras compatibles con JSON y reconstruirlos con `model_validate()`.
2. Añadir un nodo `ChooseRetrievalMode` que distinga búsqueda semántica,
   híbrida, fecha máxima, recuento, consulta exhaustiva y línea temporal.
3. Desacoplar la lectura de checkpoints de `loader()` para que el inspector no
   cargue BGE-M3 ni abra Chroma innecesariamente.
4. Añadir después historial conversacional y resolución de preguntas
   dependientes de turnos anteriores.

La serialización se abordará primero porque afecta a la durabilidad de todos
los checkpoints y a los nuevos campos que se incorporen posteriormente al
estado. La selección del modo de consulta será la siguiente mejora funcional.
La optimización del inspector no bloquea la calidad de las respuestas y puede
resolverse después o aprovechar una refactorización de la construcción del
grafo.

### Serialización segura completada

- `GraphState` dejó de almacenar instancias de `BouncerDecision`,
  `DeterministicAnalysis`, `FilterReview` y `FilterProposal`.
- La decisión del bouncer se guarda como una cadena `GO` o `NO GO`.
- El análisis, la revisión y la propuesta se guardan como diccionarios
  compatibles con JSON mediante `model_dump(mode="json")`.
- Los nodos reconstruyen temporalmente los modelos necesarios con
  `model_validate()` antes de llamar a las funciones de negocio.
- El parser, el revisor y el generador de filtros mantienen sus contratos
  Pydantic; el cambio afecta únicamente a la frontera persistida del grafo.
- Se validaron las rutas `NO GO`, `keep`, `replace` y `clarify` con bases SQLite
  temporales y `LANGGRAPH_STRICT_MSGPACK=true`.
- Al cerrar y reabrir las bases, los campos persistidos fueron `str` y `dict` y
  no se produjeron advertencias por tipos personalizados.
- La ruta `replace` reconstruyó correctamente la propuesta y produjo el filtro
  geográfico `$or` esperado.
- La suite completa mantiene 53 pruebas superadas.

### Próxima sesión

Diseñar e implementar `ChooseRetrievalMode`. El primer contrato deberá
distinguir como mínimo búsqueda semántica o híbrida, fecha máxima, recuento,
consulta exhaustiva y línea temporal. Las respuestas agregadas no dependerán
de que el registro pertinente aparezca accidentalmente entre los `top_k`
semánticos.

## 2026-08-11 — Retrieval exacto con SQLite

### Objetivo

Evitar que preguntas globales o agregadas dependan de los `top_k` semánticos y
preparar contratos comunes antes de ampliar el grafo.

### Trabajo realizado

- Se creó `retrieval_mode.py` con selección determinista de los modos
  `hybrid`, `min_max`, `count` y `timeline`.
- Las consultas de mínimos y máximos conservan la operación solicitada y los
  recuentos distinguen `incidents`, `snapshots` y `reports` a partir del
  sustantivo de la pregunta.
- Se creó `metadata_store.py`, que construye
  `data/metadata/miteco_metadata.sqlite` desde `fire_snapshots.jsonl` mediante
  un `upsert` idempotente e índices por fecha, geografía e incidente.
- JSONL, SQLite y Chroma se comprobaron con 149 snapshots coincidentes.
- Se creó `metadata_queries.py` para traducir el `final_where` de Chroma a SQL
  parametrizado. La lista cerrada de campos y operadores impide introducir
  columnas u operaciones arbitrarias desde una salida LLM.
- `get_extreme_report_date()` aplica primero los filtros y calcula después
  `MIN` o `MAX`; `get_extreme_snapshot_ids()` recupera todos los empates de la
  fecha extrema.
- `count_matches()` utiliza `COUNT(DISTINCT incident_key)`, `COUNT(*)` o
  `COUNT(DISTINCT source_sha256)` según el objetivo solicitado.
- `retrieval_chroma.py` define ahora un `RetrievalResult` plano y común. El
  retrieval híbrido normaliza la respuesta anidada de Chroma;
  `retrieve_min_max()` combina SQLite con recuperación de documentos por ID;
  `retrieve_count()` devuelve un agregado exacto sin cargar Chroma ni BGE-M3.
- `generate_context()` incorpora resultados estructurados y chunks con una
  única función. `generate_answer()` utiliza los estados generales
  `WITH_DATA` y `NO_DATA`, por lo que un recuento exacto igual a cero continúa
  siendo información válida.
- La base de metadatos se añadió al `.gitignore` y se documentó como artefacto
  local regenerable, separado de los checkpoints de LangGraph.

### Validación

- La fecha máxima de una provincia se calcula dentro de los registros ya
  filtrados, no a partir de la fecha máxima global.
- SQLite utilizó los índices `idx_fire_report_date` e
  `idx_fire_province_date` en las consultas de extremos comprobadas.
- Los IDs obtenidos para la fecha máxima de León coincidieron con los
  documentos recuperados por Chroma.
- Sobre la base actual, León contiene 14 `incident_key`, 27 snapshots y 15
  informes distintos, lo que confirma que los tres recuentos no se mezclan.
- Las pruebas cubren filtros SQL anidados, parametrización, operaciones
  inválidas, empates de fecha, ausencia de resultados y recuentos iguales a
  cero.
- La suite completa finalizó con 108 pruebas superadas y cinco advertencias
  externas de SWIG.

### Decisiones y pendientes

- El `final_where` conserva la sintaxis de Chroma como representación común;
  solo las funciones SQL lo traducen internamente.
- La eliminación de filas SQLite obsoletas cuando desaparezca un snapshot del
  JSONL queda aplazada.
- `timeline` está identificado por el selector, pero todavía no dispone de un
  retrieval específico.
- No se han conectado aún `min_max` y `count` a los puntos de entrada ni al
  grafo.

### Próxima sesión

1. Cargar o inyectar la conexión de metadatos sin guardarla en `GraphState`.
2. Ejecutar `choose_retrieval_mode()` en el flujo lineal y en LangGraph.
3. Elegir entre `retrieve()`, `retrieve_min_max()` y `retrieve_count()` según
   el plan calculado.
4. Cambiar `raw_context` de `QueryResult` a `RetrievalResult` en el estado del
   grafo.
5. Conservar una única ruta posterior por `GenerateContext` y
   `GenerateAnswer`.
6. Añadir pruebas de routing antes de abordar el modo `timeline`.
