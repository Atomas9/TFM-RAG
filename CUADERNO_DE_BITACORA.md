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
