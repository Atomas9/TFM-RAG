

# ------------------
# IMPORTS   
# ------------------
from pathlib import Path
from pydantic import BaseModel, Field
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
LOCATION_PREFIXES = ("localizacion:",)
SUMMARY_PREFIX = "actuaciones de los medios del ministerio" #texto que marca el resumen final del documento, cuando aparece, ya no hay más incendios

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

FOREIGN_COUNTRIES = {
    "portugal": "PT",
}

COMMUNITY_ALIASES_RAW = {
    "ANDALUCIA": "Andalucía",
    "ARAGON": "Aragón",
    "ASTURIAS": "Asturias",
    "PRINCIPADO DE ASTURIAS": "Asturias",
    "CANTABRIA": "Cantabria",
    "CASTILLA-LA MANCHA": "Castilla-La Mancha",
    "CASTILLA LA MANCHA": "Castilla-La Mancha",
    "CASTILLA Y LEON": "Castilla y León",
    "CATALUÑA": "Cataluña",
    "CATALUNYA": "Cataluña",
    "CEUTA": "Ceuta",
    "C. VALENCIANA": "Comunitat Valenciana",
    "COMUNIDAD VALENCIANA": "Comunitat Valenciana",
    "COMUNITAT VALENCIANA": "Comunitat Valenciana",
    "EXTREMADURA": "Extremadura",
    "GALICIA": "Galicia",
    "ISLAS BALEARES": "Illes Balears",
    "ILLES BALEARS": "Illes Balears",
    "LA RIOJA": "La Rioja",
    "MADRID": "Comunidad de Madrid",
    "COMUNIDAD DE MADRID": "Comunidad de Madrid",
    "MELILLA": "Melilla",
    "MURCIA": "Región de Murcia",
    "REGION DE MURCIA": "Región de Murcia",
    "NAVARRA": "Navarra",
    "COMUNIDAD FORAL DE NAVARRA": "Navarra",
    "PAIS VASCO": "País Vasco",
    "EUSKADI": "País Vasco",
    "CANARIAS": "Canarias",
}



# Cada provincia se asocia también con su comunidad. Se incluyen variantes
# castellanas y cooficiales frecuentes en los documentos.
PROVINCES_RAW = {
    "A CORUÑA": ("A Coruña", "Galicia"),
    "CORUÑA": ("A Coruña", "Galicia"),
    "ALAVA": ("Álava", "País Vasco"),
    "ARABA": ("Álava", "País Vasco"),
    "ALBACETE": ("Albacete", "Castilla-La Mancha"),
    "ALICANTE": ("Alicante", "Comunitat Valenciana"),
    "ALACANT": ("Alicante", "Comunitat Valenciana"),
    "ALMERIA": ("Almería", "Andalucía"),
    "ASTURIAS": ("Asturias", "Asturias"),
    "AVILA": ("Ávila", "Castilla y León"),
    "BADAJOZ": ("Badajoz", "Extremadura"),
    "BARCELONA": ("Barcelona", "Cataluña"),
    "BIZKAIA": ("Bizkaia", "País Vasco"),
    "VIZCAYA": ("Bizkaia", "País Vasco"),
    "BURGOS": ("Burgos", "Castilla y León"),
    "CACERES": ("Cáceres", "Extremadura"),
    "CADIZ": ("Cádiz", "Andalucía"),
    "CANTABRIA": ("Cantabria", "Cantabria"),
    "CASTELLON": ("Castellón", "Comunitat Valenciana"),
    "CASTELLO": ("Castellón", "Comunitat Valenciana"),
    "CEUTA": ("Ceuta", "Ceuta"),
    "CIUDAD REAL": ("Ciudad Real", "Castilla-La Mancha"),
    "CORDOBA": ("Córdoba", "Andalucía"),
    "CUENCA": ("Cuenca", "Castilla-La Mancha"),
    "GIRONA": ("Girona", "Cataluña"),
    "GERONA": ("Girona", "Cataluña"),
    "GRANADA": ("Granada", "Andalucía"),
    "GUADALAJARA": ("Guadalajara", "Castilla-La Mancha"),
    "GIPUZKOA": ("Gipuzkoa", "País Vasco"),
    "GUIPUZCOA": ("Gipuzkoa", "País Vasco"),
    "HUELVA": ("Huelva", "Andalucía"),
    "HUESCA": ("Huesca", "Aragón"),
    "ILLES BALEARS": ("Illes Balears", "Illes Balears"),
    "BALEARES": ("Illes Balears", "Illes Balears"),
    "JAEN": ("Jaén", "Andalucía"),
    "LA RIOJA": ("La Rioja", "La Rioja"),
    "LAS PALMAS": ("Las Palmas", "Canarias"),
    "LEON": ("León", "Castilla y León"),
    "LLEIDA": ("Lleida", "Cataluña"),
    "LERIDA": ("Lleida", "Cataluña"),
    "LUGO": ("Lugo", "Galicia"),
    "MADRID": ("Madrid", "Comunidad de Madrid"),
    "MALAGA": ("Málaga", "Andalucía"),
    "MELILLA": ("Melilla", "Melilla"),
    "MURCIA": ("Murcia", "Región de Murcia"),
    "NAVARRA": ("Navarra", "Navarra"),
    "OURENSE": ("Ourense", "Galicia"),
    "ORENSE": ("Ourense", "Galicia"),
    "PALENCIA": ("Palencia", "Castilla y León"),
    "PONTEVEDRA": ("Pontevedra", "Galicia"),
    "SALAMANCA": ("Salamanca", "Castilla y León"),
    "SANTA CRUZ DE TENERIFE": ("Santa Cruz de Tenerife", "Canarias"),
    "SEGOVIA": ("Segovia", "Castilla y León"),
    "SEVILLA": ("Sevilla", "Andalucía"),
    "SORIA": ("Soria", "Castilla y León"),
    "TARRAGONA": ("Tarragona", "Cataluña"),
    "TERUEL": ("Teruel", "Aragón"),
    "TOLEDO": ("Toledo", "Castilla-La Mancha"),
    "VALENCIA": ("Valencia", "Comunitat Valenciana"),
    "VALENCIA/VALENCIA": ("Valencia", "Comunitat Valenciana"),
    "VALLADOLID": ("Valladolid", "Castilla y León"),
    "ZAMORA": ("Zamora", "Castilla y León"),
    "ZARAGOZA": ("Zaragoza", "Aragón"),
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

class FireBlock(BaseModel):
    """Grupo de líneas que ya sabemos que pertenecen al mismo incendio."""
    ordinal: int = Field(ge=1)
    country: str
    autonomous_community: str | None
    province: str | None
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    lines: list[PDFLine]

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

AUTONOMOUS_COMMUNITIES = {
    normalize_text(alias): canonical
    for alias, canonical in COMMUNITY_ALIASES_RAW.items()
}

PROVINCE_TO_COMMUNITY = {
    normalize_text(alias): value
    for alias, value in PROVINCES_RAW.items()
}



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

def is_location_start(line: PDFLine) -> bool:
    """
    La normalización ya ha eliminado el acento de Localización.
    Devuelve True si la línea comienza con "localizacion:".
    """

    return line.normalized_text.startswith(LOCATION_PREFIXES)

def is_summary_start(line: PDFLine) -> bool:
    """
    Marca el límite final de los bloques de incendios.
    Devuelve True si la línea comienza con "actuaciones de los medios del ministerio".
    """

    return line.normalized_text.startswith(SUMMARY_PREFIX)

def split_fire_blocks(lines: list[PDFLine]) -> list[FireBlock]:
    """Delimita un bloque por incendio conservando la geografía vigente."""

    blocks: list[FireBlock] = []

    current_country = "ES"
    current_community: str | None = None
    current_province: str | None = None

    # Estos valores solo existen mientras hay un incendio abierto.
    current_lines: list[PDFLine] = []
    block_country = "ES"
    block_community: str | None = None
    block_province: str | None = None

    def close_current_block() -> None:
        """Cierra el bloque abierto utilizando una copia de su estado."""

        nonlocal current_lines

        if not current_lines:
            return

        blocks.append(
            FireBlock(
                ordinal=len(blocks) + 1,
                country=block_country,
                autonomous_community=block_community,
                province=block_province,
                page_start=current_lines[0].page_number,
                page_end=current_lines[-1].page_number,
                lines=list(current_lines),
            )
        )
        current_lines = []

    for line in lines:
        normalized = line.normalized_text

        # El resumen estadístico no pertenece al último incendio.
        if is_summary_start(line):
            close_current_block()
            break

        # "OTRO PAIS" anuncia que el encabezado siguiente no es español.
        if normalized == "otro pais":
            close_current_block()
            current_country = "OTHER"
            current_community = None
            current_province = None
            continue

        # Después de OTRO PAIS reconocemos el nombre del país.
        if current_country != "ES" and normalized in FOREIGN_COUNTRIES:
            close_current_block()
            current_country = FOREIGN_COUNTRIES[normalized]
            current_community = None
            current_province = line.clean_text
            continue

        province_candidate = PROVINCE_TO_COMMUNITY.get(normalized)
        community_candidate = AUTONOMOUS_COMMUNITIES.get(normalized)

        # Asturias, Madrid, Murcia, Navarra y La Rioja pueden ser a la vez
        # comunidad y provincia. Si la comunidad ya está activa, la segunda
        # aparición se interpreta como provincia.
        if (
            province_candidate
            and current_community == province_candidate[1]
        ):
            close_current_block()
            current_country = "ES"
            current_province = province_candidate[0]
            continue

        if community_candidate:
            close_current_block()
            current_country = "ES"
            current_community = community_candidate
            current_province = None
            continue

        if province_candidate:
            close_current_block()
            current_country = "ES"
            current_province, current_community = province_candidate
            continue

        if is_location_start(line):
            # Una nueva Localización siempre cierra el incendio anterior.
            close_current_block()

            # Congelamos la geografía para que cambios posteriores no alteren
            # retroactivamente este bloque.
            block_country = current_country
            block_community = current_community
            block_province = current_province
            current_lines = [line]
            continue

        # Solo guardamos contenido cuando ya se ha abierto un incendio.
        if current_lines:
            current_lines.append(line)

    # Seguridad para documentos que terminen sin marcador de resumen.
    close_current_block()

    if not blocks:
        raise ValueError("No se encontraron bloques iniciados por Localización:")

    return blocks

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

sample_blocks = split_fire_blocks(pdf1_lines)
print("Bloques encontrados:", len(sample_blocks))
for block in sample_blocks[:3]:
    print(
        block.ordinal,
        block.autonomous_community,
        block.province,
        block.lines[0].cleaned_text,
    )









