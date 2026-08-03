# Librerías utilizadas en MITECO Fire RAG

Este documento explica qué papel tiene cada librería del proyecto, cómo se
importa y cuáles son las funciones o clases que utilizaremos con más
frecuencia. No todas se usan todavía: las primeras intervienen en el parseo de
los PDF y las restantes se incorporarán en las siguientes fases del RAG.

Las versiones compatibles están centralizadas en
[`requirements.txt`](../../requirements.txt). No conviene instalar paquetes
sueltos sin actualizar también ese archivo.

## 1. Cómo leer una llamada de Python

En esta expresión:

```python
document = pymupdf.open(pdf_path)
```

- `pymupdf` es el módulo que hemos importado.
- `open` es una función proporcionada por ese módulo.
- `pdf_path` es el argumento que le entregamos.
- el resultado se guarda en `document`.

En cambio, en:

```python
page_text = page.get_text("text")
```

`page` es un objeto y `get_text()` es uno de sus métodos. Un método es una
función asociada a un objeto concreto.

## 2. Biblioteca estándar de Python

Estos módulos vienen incluidos con Python. Se importan, pero **no** se añaden a
`requirements.txt` ni se instalan con `pip`.

### `pathlib`: rutas y archivos

`Path` representa una ruta como un objeto, lo que evita construir rutas
manualmente como cadenas de texto.

```python
from pathlib import Path

input_dir = Path("data/raw/miteco")
pdfs = sorted(input_dir.glob("*.pdf"))

for pdf_path in pdfs:
    print(pdf_path.name)   # parte_2025_07_14.pdf
    print(pdf_path.stem)   # parte_2025_07_14
    print(pdf_path.exists())
```

Operaciones que usamos:

- `Path(...)`: crea el objeto que representa la ruta.
- `.exists()`: comprueba si existe.
- `.glob("*.pdf")`: busca los PDF de una carpeta.
- `.name`: devuelve el nombre con extensión.
- `.stem`: devuelve el nombre sin extensión.
- `.open("rb")`: abre el archivo en modo binario.

### `re`: expresiones regulares

Permite buscar patrones variables en el texto. Es útil porque una fecha puede
ser `5 de julio de 2025` y otra `05/07/2025`.

```python
import re

date_pattern = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
match = date_pattern.search("Fecha: 14/07/2025")

if match:
    day = int(match.group(1))
```

- `re.compile(...)`: prepara un patrón para reutilizarlo.
- `.search(text)`: busca la primera coincidencia en cualquier lugar del texto.
- `.group(n)`: recupera uno de los grupos entre paréntesis.
- `re.sub(pattern, replacement, text)`: sustituye coincidencias.
- El prefijo `r` crea una *raw string* y facilita escribir símbolos como `\d`
  o `\s`.

En `clean_line()` usamos:

```python
re.sub(r"\s+", " ", line).strip()
```

`\s+` significa «uno o más caracteres de espacio»; por tanto, varios espacios,
tabuladores o saltos internos se convierten en un solo espacio.

### `unicodedata`: normalización de texto

Ayuda a comparar textos aunque unos contengan tildes y otros no.

```python
import unicodedata

decomposed = unicodedata.normalize("NFKD", "Ávila")
without_accents = "".join(
    character
    for character in decomposed
    if not unicodedata.combining(character)
)
```

- `normalize("NFKD", text)`: descompone letras y marcas diacríticas; por
  ejemplo, `á` pasa a estar representada por `a` más la tilde.
- `combining(character)`: indica si el carácter es una marca diacrítica.

La versión normalizada sirve para detectar encabezados y patrones. El texto
original o limpio debe conservarse para mostrarlo al usuario.

### `hashlib`: huella digital del PDF

Calcula un hash criptográfico. Usamos SHA-256 para identificar de manera
estable cada archivo y detectar duplicados o cambios.

```python
import hashlib

digest = hashlib.sha256()
digest.update(block)
sha256 = digest.hexdigest()
```

- `hashlib.sha256()`: crea el calculador.
- `.update(block)`: incorpora un bloque de bytes.
- `.hexdigest()`: devuelve el resultado como texto hexadecimal.

Leer por bloques evita cargar un PDF completo en memoria. El hash identifica el
contenido del archivo, no el incendio; varios incendios de un mismo parte
comparten `source_sha256`.

### `datetime`: fechas y horas

```python
from datetime import date, datetime, timezone

report_date = date(2025, 7, 14)
last_update = datetime.strptime(
    "2025-07-14 18:30:00",
    "%Y-%m-%d %H:%M:%S",
)
```

- `date`: guarda una fecha sin hora.
- `datetime`: guarda fecha y hora.
- `datetime.strptime(text, format)`: convierte texto a `datetime`.
- `timezone`: permite hacer explícita una zona u offset horario. Está importado
  en el parser actual, aunque todavía no se utiliza.

### `typing`: anotaciones de tipos

Las anotaciones documentan qué recibe y devuelve una función y permiten que
VS Code detecte errores antes de ejecutar el programa.

```python
from typing import Iterable, Literal

def infer_report_type(name: str) -> Literal[
    "definitivo", "provisional", "desconocido"
]:
    ...
```

- `Literal[...]`: limita un valor a varias opciones concretas.
- `Iterable[T]`: indica que se acepta cualquier objeto recorrible que produzca
  elementos de tipo `T`. Está importado en el parser, pero aún no se utiliza.
- `str | None`: significa que el valor puede ser texto o `None`.
- `list[PDFLine]`: significa lista de objetos `PDFLine`.

Las anotaciones normales no validan los datos durante la ejecución. Pydantic sí
lo hace cuando crea uno de sus modelos.

## 3. Parseo y modelado de los PDF

### PyMuPDF (`pymupdf`): lector principal de PDF

PyMuPDF abre el documento y permite recorrer sus páginas y extraer texto. Es el
lector principal elegido para la fase 1 por su velocidad y porque puede obtener
texto con información de posición cuando la necesitemos.

Se instala e importa con el mismo nombre:

```bash
python -m pip install pymupdf
```

```python
import pymupdf
```

#### `pymupdf.open()`

```python
from pathlib import Path
import pymupdf

pdf_path = Path("data/raw/miteco/parte.pdf")

with pymupdf.open(pdf_path) as document:
    print(document.page_count)
```

`pymupdf.open(pdf_path)` abre el PDF y devuelve un objeto `Document`. En la API
actual, `open()` es un alias de `pymupdf.Document()`. El bloque `with` garantiza
que el archivo se cierre incluso si ocurre una excepción.

#### Recorrer páginas y extraer texto

```python
with pymupdf.open(pdf_path) as document:
    for page_number, page in enumerate(document, start=1):
        page_text = page.get_text("text")
```

- `document` es iterable: cada vuelta entrega un objeto `Page`.
- `enumerate(..., start=1)` añade el número humano de página desde 1.
- `page.get_text("text")` devuelve el texto plano de la página.
- `page.get_text("words")` devuelve palabras y sus coordenadas.
- `page.get_text("blocks")` devuelve bloques de texto y sus coordenadas.
- `page.get_text("dict")` devuelve una estructura detallada de bloques, líneas,
  fragmentos tipográficos y posiciones.
- `sort=True` puede ordenar el resultado aproximadamente de arriba abajo y de
  izquierda a derecha.

Para nuestro primer parser, `"text"` es suficiente. Si el orden visual del PDF
no coincide con el texto extraído, probaremos `blocks`, `words` o `dict` antes
de intentar corregirlo con reglas frágiles.

Importante: PyMuPDF extrae la capa de texto existente; no realiza OCR. Un PDF
formado solamente por imágenes necesitaría una fase adicional de OCR.

Documentación oficial: [Document y `pymupdf.open()`](https://pymupdf.readthedocs.io/en/latest/document.html) y
[`Page.get_text()`](https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_text).

### Pydantic: modelos de datos validados

Pydantic permite definir la forma exacta de nuestros datos. Cada línea, cada
documento y, más adelante, cada incendio tendrá un modelo explícito.

```python
from pydantic import BaseModel, ConfigDict, Field

class PDFLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    line_number: int = Field(ge=1)
    raw_text: str
    cleaned_text: str
    normalized_text: str
```

#### ¿Qué significa `(BaseModel)`?

```python
class PDFLine(BaseModel):
```

`PDFLine` hereda de `BaseModel`. Así recibe automáticamente el constructor, la
validación, la conversión controlada de tipos, mensajes de error descriptivos y
métodos de serialización.

```python
line = PDFLine(
    page_number=1,
    line_number=3,
    raw_text="  Localización: Ávila ",
    cleaned_text="Localización: Ávila",
    normalized_text="localizacion: avila",
)

print(line.page_number)   # acceso a un atributo
print(line.model_dump())  # conversión a diccionario
```

Si un dato incumple el modelo, Pydantic genera `ValidationError`:

```python
from pydantic import ValidationError

try:
    PDFLine(
        page_number="no es un número",
        line_number=1,
        raw_text="texto",
        cleaned_text="texto",
        normalized_text="texto",
    )
except ValidationError as error:
    print(error)
```

Elementos importantes:

- `BaseModel`: clase base de nuestros modelos.
- `Field(...)`: añade reglas; por ejemplo, `Field(ge=1)` exige un valor mayor o
  igual que 1.
- `ConfigDict(extra="forbid")`: rechaza campos inesperados por errores de
  escritura.
- `.model_dump()`: transforma el modelo en un diccionario.
- `.model_dump_json()`: lo serializa como JSON.
- `ValidationError`: reúne los errores de validación.

Pydantic valida la **estructura**. No puede saber por sí solo si `Ávila` es la
provincia correcta o si una fecha pertenece realmente al parte; esas son reglas
de negocio que debemos programar y probar.

Documentación oficial: [modelos de Pydantic](https://docs.pydantic.dev/latest/concepts/models/).

### pypdf: lector alternativo y compatibilidad

`pypdf` también permite leer y manipular PDF en Python puro:

```python
from pypdf import PdfReader

reader = PdfReader(pdf_path)
for page in reader.pages:
    text = page.extract_text()
```

En este proyecto PyMuPDF es el lector principal. `pypdf` se mantiene de momento
porque el prototipo anterior lo utilizaba y puede servir para comparar una
extracción problemática. No debemos mezclar los objetos `Page` de ambas
librerías como si fueran del mismo tipo.

Documentación oficial: [extracción de texto con pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

## 4. Descarga de los partes

Estas librerías se usarán cuando automaticemos el descubrimiento y la descarga
desde MITECO.

### HTTPX: peticiones HTTP

Descarga páginas HTML y archivos mediante HTTP/HTTPS.

```python
import httpx

with httpx.Client(
    timeout=30.0,
    follow_redirects=True,
) as client:
    response = client.get(pdf_url)
    response.raise_for_status()
    pdf_bytes = response.content
```

- `httpx.Client(...)`: reutiliza conexiones y configuración.
- `.get(url)`: realiza una petición GET.
- `.raise_for_status()`: lanza una excepción si la respuesta es un error HTTP.
- `.text`: contenido decodificado como texto.
- `.content`: contenido binario, necesario para un PDF.
- `timeout`: evita esperar indefinidamente.

Documentación oficial: [guía rápida de HTTPX](https://www.python-httpx.org/quickstart/).

### Beautiful Soup (`beautifulsoup4` / `bs4`): análisis de HTML

El nombre instalado y el importado son distintos:

```bash
python -m pip install beautifulsoup4
```

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(response.text, "html.parser")

for link in soup.find_all("a", href=True):
    href = link.get("href")
```

- `BeautifulSoup(html, "html.parser")`: convierte HTML en un árbol navegable.
- `.find(...)`: devuelve la primera coincidencia.
- `.find_all(...)`: devuelve todas las coincidencias.
- `.select(...)`: busca con selectores CSS.
- `.get("href")`: lee un atributo sin fallar si no existe.

HTTPX trae el HTML; Beautiful Soup lo interpreta. Ninguna de las dos debería
usarse para extraer el contenido interno de un PDF.

Documentación oficial: [Beautiful Soup 4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/).

## 5. Normalización geográfica y coincidencia aproximada

### RapidFuzz: comparación de nombres parecidos

Ayudará a relacionar variantes como errores tipográficos o nombres con pequeñas
diferencias con un catálogo oficial de municipios y provincias.

```python
from rapidfuzz import fuzz, process

score = fuzz.ratio("san bartolome", "san bartolomé")

best_match = process.extractOne(
    "navalperal d tormes",
    municipality_names,
    scorer=fuzz.WRatio,
    score_cutoff=85,
)
```

- `fuzz.ratio(a, b)`: calcula similitud entre dos textos.
- `fuzz.WRatio`: combina varias estrategias de comparación.
- `process.extractOne(...)`: encuentra el mejor candidato.
- `score_cutoff`: impide aceptar coincidencias demasiado débiles.

No se debe guardar automáticamente una coincidencia dudosa. Guardaremos también
el texto original, la puntuación y, si procede, un indicador de revisión.

Documentación oficial: [RapidFuzz](https://rapidfuzz.github.io/RapidFuzz/).

## 6. Embeddings y cálculo numérico

### NumPy: vectores y matrices

NumPy aporta el tipo `ndarray`, usado para cálculos numéricos eficientes. Los
embeddings son, en esencia, vectores de números.

```python
import numpy as np

embedding = np.asarray(embedding, dtype=np.float32)
print(embedding.shape)
```

En nuestro entorno está fijado a `numpy==1.26.4` por compatibilidad con la wheel
de PyTorch disponible para macOS Intel.

Documentación oficial: [inicio rápido de NumPy](https://numpy.org/doc/stable/user/quickstart.html).

### PyTorch (`torch`): motor de cálculo de los modelos

PyTorch ejecuta las operaciones tensoriales de los modelos de embeddings.
Normalmente Sentence Transformers lo utilizará por debajo:

```python
import torch

device = "mps" if torch.backends.mps.is_available() else "cpu"

with torch.no_grad():
    # inferencia sin calcular gradientes
    ...
```

- `Tensor`: estructura multidimensional usada por los modelos.
- `torch.no_grad()`: evita guardar gradientes durante inferencia.
- `torch.backends.mps.is_available()`: comprueba la aceleración MPS en equipos
  Apple compatibles.

En este Mac Intel se usa PyTorch 2.2.2 por disponibilidad de paquetes
precompilados. No se debe actualizar de forma aislada.

Documentación oficial: [PyTorch](https://pytorch.org/docs/stable/index.html).

### Transformers: arquitectura y componentes de los modelos

Hugging Face Transformers proporciona configuraciones, tokenizadores y modelos
preentrenados. Sentence Transformers se apoya en ella.

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
tokens = tokenizer("Incendio en Ávila", return_tensors="pt")
```

- `from_pretrained(model_id)`: descarga o carga desde caché los archivos del
  modelo.
- El tokenizador convierte texto en identificadores que entiende el modelo.
- El modelo transforma esos identificadores en representaciones numéricas.

Para crear los embeddings del RAG utilizaremos directamente la interfaz más
sencilla de Sentence Transformers, no llamadas manuales al modelo base.

Documentación oficial: [Transformers](https://huggingface.co/docs/transformers/index).

### Sentence Transformers: creación de embeddings

Convierte textos completos en vectores semánticos comparables.

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3", device="cpu")
embeddings = model.encode(
    texts,
    batch_size=8,
    normalize_embeddings=True,
    show_progress_bar=True,
)
```

- `SentenceTransformer(model_id, device="cpu")`: carga el modelo y fuerza su
  ejecucion en CPU, como hace el script actual.
- `.encode(texts)`: genera un vector por texto.
- `batch_size`: número de textos procesados juntos.
- `normalize_embeddings=True`: normaliza los vectores; debe ser coherente entre
  indexación y consulta.

Un embedding se usará para similitud semántica. Provincia, fecha, comunidad o
estado se guardarán además como metadatos estructurados; no hay que confiar en
el embedding para aplicar filtros exactos.

Documentación oficial: [`SentenceTransformer.encode()`](https://sbert.net/docs/package_reference/sentence_transformer/SentenceTransformer.html#sentence_transformers.SentenceTransformer.encode).

## 7. Almacenamiento y recuperación

### ChromaDB (`chromadb`): base de datos vectorial

Chroma guardará juntos el texto, su embedding, un identificador y los
metadatos del incendio.

```python
import chromadb

client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_or_create_collection(
    name="MITECO_fire_snapshots",
    embedding_function=None,
)

collection.upsert(
    ids=[snapshot.snapshot_id],
    documents=[chunk_text],
    embeddings=[embedding.tolist()],
    metadatas=[{
        "province": "Ávila",
        "report_date": "2025-07-14",
    }],
)
```

Consulta semántica con filtro de metadatos:

```python
results = collection.query(
    query_embeddings=[query_embedding.tolist()],
    n_results=5,
    where={"province": "Ávila"},
)
```

- `PersistentClient(path=...)`: guarda la colección en disco.
- `get_or_create_collection(name)`: obtiene o crea una colección.
- `embedding_function=None`: indica que el proyecto proporciona sus propios
  vectores.
- `.upsert(...)`: inserta un ID nuevo o actualiza uno existente.
- `.query(...)`: recupera los más próximos al vector consultado.
- `where={...}`: aplica filtros sobre metadatos.

Como calcularemos los embeddings nosotros, siempre entregaremos explícitamente
`embeddings` y `query_embeddings`. Los nombres y tipos de los metadatos deben
ser consistentes; por ejemplo, no mezclar `province`, `provincia` y `Provincia`.
`upsert()` no elimina los registros antiguos que ya no estén presentes en la
nueva entrada; esa sincronización debe programarse por separado.

Documentación oficial: [Chroma](https://docs.trychroma.com/docs/overview/introduction).

## 8. Generación de la respuesta

### Ollama: cliente del LLM

El paquete de Python comunica la aplicación con un modelo servido por Ollama,
ya sea en el servicio configurado localmente o en la nube.

```python
from ollama import Client

client = Client(host=ollama_host)
response = client.chat(
    model=model_name,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question_with_context},
    ],
)

answer = response["message"]["content"]
```

- `Client(...)`: configura la conexión con el servidor.
- `.chat(...)`: envía una conversación al modelo.
- `model`: modelo configurado para la aplicación.
- `messages`: lista de mensajes con rol y contenido.

El LLM no buscará directamente en Chroma. Nuestro programa recuperará primero
los incendios relevantes, construirá un contexto con sus fuentes y después se
lo entregará al modelo. La dirección del servicio y las credenciales se
guardarán en variables de entorno, nunca en Git.

Documentación oficial: [cliente Python de Ollama](https://github.com/ollama/ollama-python).

## 9. LangGraph: orquestación del workflow

LangGraph organiza un proceso como un conjunto de nodos conectados mediante
aristas. No genera embeddings, no consulta Chroma y no sustituye las llamadas a
Ollama: decide qué función se ejecuta y conserva el estado compartido.

```python
graph = StateGraph(GraphState)
graph.add_node("Bouncer", bouncer_node)
graph.add_edge(START, "Bouncer")
compiled_graph = graph.compile()
```

- `StateGraph(GraphState)`: crea un grafo cuyo estado sigue el esquema
  `GraphState`.
- `.add_node(nombre, funcion)`: registra la función ejecutada en una fase.
- `.add_edge(origen, destino)`: crea una transición fija.
- `.add_conditional_edges(...)`: elige la transición mediante una función de
  routing.
- `.compile(...)`: valida las conexiones y produce el grafo ejecutable.
- `.invoke(entrada, config)`: ejecuta el workflow y devuelve el estado final.
- `MemorySaver`: conserva checkpoints mientras el proceso sigue abierto.

En este proyecto, `functools.partial` configura los nodos que necesitan el
catálogo, el modelo de embeddings o la colección. Esos recursos no se guardan
en el estado porque son dependencias pesadas y no resultados trazables.

Documentación oficial: [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api).

## 10. Pruebas y notebooks

### pytest: pruebas automatizadas

Sirve para comprobar que un cambio no rompe los casos ya resueltos.

```python
def test_clean_line_removes_extra_spaces():
    assert clean_line("  Incendio   en Ávila  ") == "Incendio en Ávila"
```

Se ejecuta desde la raíz del proyecto:

```bash
python -m pytest
```

Para el parser prepararemos pruebas con fechas, límites de incendios,
localizaciones heredadas y documentos mal formados.

Documentación oficial: [pytest](https://docs.pytest.org/en/stable/).

### IPython Kernel (`ipykernel`): ejecución de notebooks

Es el proceso que ejecuta las celdas de un notebook con el Python del entorno
`RAG-TFM`. Normalmente no lo importamos en el código.

Para registrar el entorno como kernel:

```bash
python -m ipykernel install --user \
  --name RAG-TFM \
  --display-name "Python (RAG-TFM)"
```

En VS Code hay que seleccionar `Python (RAG-TFM)` como kernel del notebook.

Documentación oficial: [instalación de IPython Kernel](https://ipython.readthedocs.io/en/stable/install/kernel_install.html).

### nbformat: estructura de archivos `.ipynb`

Permite leer, crear y validar notebooks mediante código:

```python
import nbformat

notebook = nbformat.read(
    "notebooks/01_fase1_parseo_miteco.ipynb",
    as_version=4,
)
nbformat.validate(notebook)
```

No interviene en el parser ni en el RAG. Está instalado para mantener y validar
los apuntes ejecutables del proyecto.

Documentación oficial: [nbformat](https://nbformat.readthedocs.io/en/latest/).

## 11. Mapa rápido por fases

| Fase | Librerías principales | Resultado |
|---|---|---|
| Descarga | HTTPX, Beautiful Soup | PDF originales en `data/raw/miteco` |
| Lectura y parseo | PyMuPDF, Pydantic, `re`, `pathlib`, `unicodedata`, `hashlib` | Un registro validado por incendio |
| Normalización geográfica | RapidFuzz | Metadatos geográficos homogéneos |
| Embeddings | Sentence Transformers, Transformers, PyTorch, NumPy | Un vector por chunk |
| Persistencia y búsqueda | ChromaDB | Consulta semántica y por metadatos |
| Generación | Ollama | Respuesta basada en el contexto recuperado |
| Orquestación | LangGraph | Estado, nodos, rutas y checkpoints del workflow |
| Calidad | pytest, ipykernel, nbformat | Pruebas y apuntes reproducibles |

## 12. Qué conviene aprender primero

Una vez completado el primer parser y el primer índice, el orden más útil es:

1. `Path` y recorrido de archivos.
2. `pymupdf.open()`, `Document`, `Page` y `Page.get_text()`.
3. Modelos Pydantic derivados de `BaseModel`.
4. Listas, bucles y `enumerate()`.
5. Expresiones regulares con `compile()`, `search()` y `group()`.
6. `SentenceTransformer.encode()` y normalización de vectores.
7. `PersistentClient`, colecciones, `upsert()`, `get()` y `query()` de Chroma.
8. Funciones pequeñas y pruebas con pytest.

El siguiente aprendizaje práctico es generar el embedding de una pregunta y
usar `collection.query()` con y sin `where`. Ollama puede esperar hasta haber
comprobado que el recuperador devuelve snapshots pertinentes y trazables.
