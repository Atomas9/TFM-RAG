

# ------------------
# IMPORTS   
# ------------------
from pathlib import Path
from pydantic import BaseModel
from datetime import date, datetime, timezone
from typing import Iterable, Literal

import pymupdf
import re
import unicodedata
import hashlib

# ------------------
# CONSTANTES
# ------------------
INPUT_DIR = Path('data/raw/miteco')

print('------------------')
print(INPUT_DIR)
print(INPUT_DIR.exists())

# ------------------
# DICCIONARIOS
# ------------------
SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

# ------------------
# EXPRESIONES REGULARES
# ------------------
TEXTUAL_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+de\s+("
    + "|".join(SPANISH_MONTHS)
    + r")\s+de\s+(\d{4})\b"
)

NUMERIC_DATE_PATTERN = re.compile(
    r"\bfecha\s*:\s*(\d{1,2})/(\d{1,2})/(\d{4})\b"
)

LAST_UPDATE_PATTERN = re.compile(
    r"ultima\s+actualizacion\s*:\s*"
    r"(\d{1,2}:\d{2}(?::\d{2})?)\s*"
    r"(?:del\s+dia\s*)?"
    r"(\d{1,2})/(\d{1,2})/(\d{4})"
)

# ------------------
# CLASES
# ------------------
class PDFLine(BaseModel):
    page_number: int
    line_number: int
    raw_text: str
    cleaned_text: str
    normalized_text: str

class DocumentMetadata(BaseModel):
    """Datos comunes a todos los incendios de un PDF."""
    document_id: str
    source_file: str
    source_path: str
    source_sha256: str
    source_url: str | None = None
    report_type: Literal["definitivo", "provisional", "desconocido"]
    report_date: date
    last_update: datetime | None = None

# ------------------
# FUNCIONES
# ------------------
def clean_line(line: str) -> str:
    '''
    Elimina espacios sobrantes
    \s+ significa uno o más espacios, tabuladores o saltos internos.
    re.sub() pertenece al módulo re (expresiones regulares)
    Sintaxis: re.sub(patrón, reemplazo, cadena)
    .strip() elimina espacios al inicio y al final de la cadena
    '''
    return re.sub(r'\s+', ' ', line).strip() 

def normalize_text(text: str | None) -> str:
    '''
    Normaliza texto eliminando acentos y convirtiendo a minúsculas
    '''
    if not text:
        return ''
    
    decomposed = unicodedata.normalize('NFKD', text) #NFKD separa p.e. "á" en "a" y "´"
    # Eliminamos los carácteres que son marcas diacríticas
    without_accents = ''.join(
        character
        for character in decomposed
        if not unicodedata.combining(character) # True si el carácter es una marca diacrítica
    )

    return clean_line(without_accents).lower()

def calculate_sha256(path: Path, buffer_size: int = 1024 * 1024) -> str:
    """Calcula el hash por bloques para no cargar todo el PDF en memoria."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        while block := file.read(buffer_size):
            digest.update(block)

    return digest.hexdigest()

def extract_pdf_lines(pdf_path: Path):
    if not pdf_path.exists():
        raise FileNotFoundError(f"El archivo {pdf_path} no existe.")
    
    extracted_lines = []

    with pymupdf.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text('text')
            for line_number, raw_line in enumerate(page_text.splitlines(), start=1):
                cleaned_line = clean_line(raw_line)
                if not cleaned_line:
                    continue

                extracted_lines.append(
                    PDFLine(
                        page_number=page_number,
                        line_number=line_number,
                        raw_text=raw_line,
                        cleaned_text=cleaned_line,
                        normalized_text=normalize_text(cleaned_line)
                    )
                )
    
    if not extracted_lines:
        raise ValueError(f'El PDF no contiene texto extraíble: {pdf_path.name}')
    
    return extracted_lines

def extract_report_date(text: str) -> date:
    '''
    Busca la fecha en el texto del informe y la devuelve como un objeto date.
    Si no se encuentra una fecha válida, lanza un ValueError.
    '''
    textual_match = TEXTUAL_DATE_PATTERN.search(text)
    if textual_match:
        day = int(textual_match.group(1))
        month = SPANISH_MONTHS[textual_match.group(2).lower()]
        year = int(textual_match.group(3))
        return date(year, month, day)
    
    numeric_match = NUMERIC_DATE_PATTERN.search(text)
    if numeric_match:
        day = int(numeric_match.group(1))
        month = int(numeric_match.group(2))
        year = int(numeric_match.group(3))
        return date(year, month, day)
    
    raise ValueError("No se pudo extraer la fecha del informe.")

def extract_last_update(text: str) -> datetime | None:
    '''
    Busca la última actualización en el texto del informe y la devuelve como un objeto datetime.
    Si no se encuentra una fecha válida, devuelve None.
    '''
    match = LAST_UPDATE_PATTERN.search(text)
    if match:
        time_text = match.group(1)
        day = int(match.group(2))
        month = int(match.group(3))
        year = int(match.group(4))

        if time_text.count(':') == 1:
            time_text += ':00'  # Añadir segundos si no están presentes
        
        return datetime.strptime(
            f"{year}-{month}-{day} {time_text}",
            "%Y-%m-%d %H:%M:%S",
        )
        
    return None

def infer_report_type(pdf_path: Path) -> Literal["definitivo", "provisional", "desconocido"]:
    '''Infiere el tipo únicamente cuando el nombre es inequívoco.'''

    normalized_name = normalize_text(pdf_path.stem) #.stem elimina la extensión (p.e. '.pdf')

    if "definitivo" in normalized_name:
        return "definitivo"
    if "provisional" in normalized_name:
        return "provisional"
    return "desconocido"

def extract_document_metadata(
    pdf_path: Path,
    lines: list[PDFLine],
    source_url: str | None = None,
) -> DocumentMetadata:
    """Construye los metadatos compartidos por todos los bloques."""

    normalized_document = "\n".join(line.normalized_text for line in lines)
    sha256 = calculate_sha256(pdf_path)

    return DocumentMetadata(
        document_id=sha256[:20],
        source_file=pdf_path.name,
        source_path=str(pdf_path),
        source_sha256=sha256,
        source_url=source_url,
        report_type=infer_report_type(pdf_path),
        report_date=extract_report_date(normalized_document),
        last_update=extract_last_update(normalized_document),
    )
# ------------------
# 
# ------------------
all_pdf = sorted(INPUT_DIR.glob('*.pdf'))
pdf1 = all_pdf[0]
pdf1_lines = extract_pdf_lines(pdf1)

print(pdf1.name)
print(f'Número de líneas extraídas: {len(pdf1_lines)}')
for line in pdf1_lines[:5]:  # Mostrar solo las primeras 5 líneas para no saturar la salida
    print(f'Página {line.page_number}, Línea {line.line_number}: {line.cleaned_text}')

sample_document = extract_document_metadata(pdf1, pdf1_lines)
print(sample_document)









