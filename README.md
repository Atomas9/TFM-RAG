# MITECO Fire RAG

Proyecto de TFM para construir un sistema RAG sobre los partes diarios de
actuaciones en incendios forestales publicados por MITECO.

El objetivo inicial es extraer los PDF, identificar cada incendio como una
unidad documental independiente y permitir consultas semanticas y consultas
estructuradas por metadatos como fecha, comunidad autonoma, provincia,
ubicacion o estado del incendio.

## Estado actual

El repositorio contiene la estructura inicial del proyecto y el entorno de
dependencias validado. En `src/miteco_rag/parseo_y_chuncking.py` ya estan
implementadas la lectura y normalizacion, los metadatos documentales, la
maquina de estados geografica y la separacion por incendios. Tambien se han
anadido extractores de localizacion, estado, situacion operativa, notas, fecha
de inicio y medios asignados. Estos datos ya se integran en un `FireSnapshot`
validado por Pydantic, con identificadores reproducibles, texto original y un
`chunk_text` autosuficiente preparado para la futura generación de embeddings.

Durante la revision se corrigieron dos accesos a `clean_text` para utilizar el
atributo correcto, `cleaned_text`. El parser ya completa el recorrido de los
ocho PDF sin errores. La delimitacion de bloques, la construcción de snapshots
y la presencia de los campos se han comprobado, aunque todavia falta validar
manualmente la exactitud de las notas y los medios extraidos y convertir estas
comprobaciones en pruebas pytest.

El material previo utilizado como referencia se conserva en `extras`, pero no
forma parte del codigo principal.

El corpus local de trabajo contiene actualmente ocho partes. La maquina de
estados delimita 48 bloques `Localizacion:`: 47 de Espana y uno de Portugal.
Los PDF y los resultados generados continuan fuera del control de versiones.

`snapshot_id` identifica de forma unica una observacion dentro de un parte.
`incident_key` es una clave heuristica para agrupar observaciones que podrian
pertenecer al mismo incendio: utiliza geografia, localizacion y fecha de inicio
cuando esta existe. No debe interpretarse todavia como una identidad definitiva
si MITECO no proporciona la fecha de inicio.

La orquestacion de la fase ya esta disponible: `parse_miteco_pdf()` transforma
un PDF en sus snapshots y `parse_pdf_directory()` procesa todos los PDF de una
carpeta en orden determinista, sin deduplicar observaciones de dias distintos.
Las rutas inexistentes o las carpetas sin PDF producen errores explicitos.

## Arquitectura prevista

1. Descarga y almacenamiento inmutable de los PDF de MITECO.
2. Extraccion de texto por paginas con PyMuPDF.
3. Parser basado en la estructura de los partes y en un estado persistente de
   comunidad y provincia.
4. Un registro o snapshot por incendio y fecha de parte.
5. Embeddings multilingues con `BAAI/bge-m3`.
6. Persistencia vectorial y filtrado de metadatos con ChromaDB.
7. Recuperacion de contexto y generacion con `gemma4:31b-cloud` mediante
   Ollama.

La decision completa esta documentada en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Estructura

```text
.
├── src/miteco_rag/             Codigo principal
├── tests/                      Pruebas automatizadas
├── notebooks/                  Apuntes y soluciones ejecutables paso a paso
├── data/
│   ├── raw/                    PDF originales, no versionados
│   ├── processed/              Registros parseados, no versionados
│   └── chroma/                 Indice vectorial local, no versionado
├── docs/                       Documentacion tecnica
├── extras/                     Codigo y documentos anteriores de referencia
├── CUADERNO_DE_BITACORA.md     Historial diario del proyecto
├── requirements.txt            Dependencias compatibles
└── .env.example                Variables configurables sin secretos
```

## Preparar el entorno

```bash
conda create --name RAG-TFM python=3.11 pip -y
conda activate RAG-TFM
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip check
```

El repositorio esta preparado para macOS Intel. `requirements.txt` selecciona
PyTorch 2.2.2 en esa plataforma y una version moderna de PyTorch en las
plataformas que disponen de wheels compatibles.

## Datos

Los PDF descargados no se suben a Git. Deben guardarse en
`data/raw/miteco/`. Consulta [data/README.md](data/README.md) para conocer las
reglas del corpus.

## Alcance inicial

- Fuente documental: partes diarios de MITECO.
- Cobertura: incendios de Espana.
- Chunking: un incendio por unidad semantica, con subdivision solo si un
  registro supera el limite del modelo de embeddings.
- Recuperacion: semantica, por metadatos y combinada.
- Generacion: respuestas fundamentadas con referencia al documento, fecha y
  pagina.

## Seguimiento

Las decisiones y avances diarios se registran en
[CUADERNO_DE_BITACORA.md](CUADERNO_DE_BITACORA.md).

La solucion comentada de la primera fase puede estudiarse y ejecutarse desde
[notebooks/01_fase1_parseo_miteco.ipynb](notebooks/01_fase1_parseo_miteco.ipynb).

La ultima revision del codigo desarrollado esta en
[docs/REVISION_FASE_1.md](docs/REVISION_FASE_1.md).

Los apuntes sobre el propósito y el uso de cada dependencia están en
[docs/apuntes/LIBRERIAS.md](docs/apuntes/LIBRERIAS.md).
