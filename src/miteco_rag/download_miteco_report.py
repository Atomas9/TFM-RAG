"""Descarga y archiva el parte definitivo diario de incendios de MITECO.

Este modulo es independiente del parser y del resto del RAG. Descubre el enlace
vigente en la web oficial, valida el PDF, extrae de su contenido la fecha del
parte y conserva una copia reproducible junto con un manifiesto JSONL.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import httpx
import pymupdf


SOURCE_PAGE_URL = (
    "https://www.miteco.gob.es/es/biodiversidad/temas/"
    "incendios-forestales/estadisticas-actuaciones.html"
)
USER_AGENT = "TFM-RAG-MITECO/0.1 (+https://github.com/Atomas9/TFM-RAG)"
MADRID_TIMEZONE = ZoneInfo("Europe/Madrid")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "miteco"
MANIFEST_FILENAME = "manifest.jsonl"

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


class DownloadError(RuntimeError):
    """Error controlado durante el descubrimiento, descarga o validacion."""


@dataclass(frozen=True)
class ReportLink:
    """Titulo y URL del parte definitivo descubierto en la pagina."""

    title: str
    url: str


@dataclass(frozen=True)
class ManifestEntry:
    """Registro auditable de una descarga o revision del parte."""

    report_date: str
    downloaded_at: str
    source_page_url: str
    source_pdf_url: str
    source_title: str
    sha256: str
    filename: str
    content_length: int
    previous_sha256: str | None = None


@dataclass(frozen=True)
class ArchiveResult:
    """Resultado de archivar el PDF."""

    status: str
    path: Path
    report_date: date
    sha256: str


def normalize_for_matching(text: str) -> str:
    """Normaliza mayusculas y tildes para comparar texto visible."""

    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().split())


def find_definitive_report_link(
    html: str,
    base_url: str = SOURCE_PAGE_URL,
) -> ReportLink:
    """Localiza el enlace cuyo texto identifica el parte definitivo."""

    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        normalized_title = normalize_for_matching(title)
        if (
            "parte definitivo de intervenciones" in normalized_title
            and "dia previo" in normalized_title
        ):
            return ReportLink(title=title, url=urljoin(base_url, anchor["href"]))

    raise DownloadError(
        "No se encontro el enlace al Parte Definitivo de Intervenciones "
        "(dia previo) en la pagina de MITECO."
    )


def create_http_client() -> httpx.Client:
    """Crea el cliente HTTP con redirecciones, reintentos y timeout."""

    transport = httpx.HTTPTransport(retries=3)
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
        transport=transport,
    )


def fetch_report(client: httpx.Client) -> tuple[ReportLink, bytes, str]:
    """Descubre el enlace actual y descarga sus bytes."""

    page_response = client.get(SOURCE_PAGE_URL)
    page_response.raise_for_status()
    report_link = find_definitive_report_link(
        page_response.text,
        str(page_response.url),
    )

    pdf_response = client.get(report_link.url)
    pdf_response.raise_for_status()
    content_type = pdf_response.headers.get("content-type", "")
    return report_link, pdf_response.content, content_type


def extract_report_date(pdf_bytes: bytes) -> date:
    """Abre el PDF y extrae la fecha del parte de su primera pagina."""

    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
            if document.page_count == 0:
                raise DownloadError("El PDF descargado no contiene paginas.")
            first_page_text = document[0].get_text()
    except DownloadError:
        raise
    except Exception as error:
        raise DownloadError(f"No se pudo abrir el PDF descargado: {error}") from error

    normalized_text = normalize_for_matching(first_page_text)
    has_expected_heading = (
        "intervenciones de medios del ministerio" in normalized_text
        and "extincion de incendios forestales" in normalized_text
    )
    if not has_expected_heading:
        raise DownloadError(
            "El PDF no contiene el encabezado esperado de intervenciones "
            "del Ministerio en incendios forestales."
        )

    date_match = re.search(
        r"\b(\d{1,2})\s+de\s+"
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|setiembre|octubre|noviembre|diciembre)"
        r"\s+de\s+(\d{4})\b",
        normalized_text,
    )
    if date_match is None:
        raise DownloadError(
            "No se pudo extraer la fecha del parte desde la primera pagina."
        )

    day, month_name, year = date_match.groups()
    try:
        return date(
            year=int(year),
            month=SPANISH_MONTHS[month_name],
            day=int(day),
        )
    except ValueError as error:
        raise DownloadError(f"La fecha extraida del PDF no es valida: {error}") from error


def validate_pdf(pdf_bytes: bytes, content_type: str = "") -> date:
    """Valida la firma, el MIME cuando existe, la estructura y el encabezado."""

    if not pdf_bytes.startswith(b"%PDF"):
        raise DownloadError("La respuesta descargada no tiene firma de archivo PDF.")

    normalized_content_type = content_type.casefold()
    if normalized_content_type and "pdf" not in normalized_content_type:
        raise DownloadError(
            f"MITECO devolvio un tipo de contenido inesperado: {content_type!r}."
        )

    return extract_report_date(pdf_bytes)


def calculate_sha256(content: bytes) -> str:
    """Calcula el hash SHA-256 de un documento."""

    return hashlib.sha256(content).hexdigest()


def load_manifest(manifest_path: Path) -> list[dict[str, object]]:
    """Carga las lineas JSON validas del manifiesto."""

    if not manifest_path.exists():
        return []

    entries: list[dict[str, object]] = []
    with manifest_path.open("r", encoding="utf-8") as manifest_file:
        for line_number, line in enumerate(manifest_file, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as error:
                raise DownloadError(
                    f"El manifiesto contiene JSON invalido en la linea "
                    f"{line_number}: {error}"
                ) from error
            if not isinstance(entry, dict):
                raise DownloadError(
                    f"La linea {line_number} del manifiesto no es un objeto JSON."
                )
            entries.append(entry)
    return entries


def find_existing_pdf_by_hash(output_dir: Path, sha256: str) -> Path | None:
    """Busca un PDF ya guardado con el mismo contenido."""

    for pdf_path in sorted(output_dir.glob("*.pdf")):
        if calculate_sha256(pdf_path.read_bytes()) == sha256:
            return pdf_path
    return None


def append_manifest_entry(manifest_path: Path, entry: ManifestEntry) -> None:
    """Añade una linea JSON al manifiesto."""

    with manifest_path.open("a", encoding="utf-8") as manifest_file:
        json.dump(asdict(entry), manifest_file, ensure_ascii=False, sort_keys=True)
        manifest_file.write("\n")


def archive_report(
    *,
    pdf_bytes: bytes,
    content_type: str,
    report_link: ReportLink,
    output_dir: Path,
    expected_date: date,
    downloaded_at: datetime | None = None,
) -> ArchiveResult:
    """Valida y archiva un parte sin duplicar documentos ya conocidos."""

    report_date = validate_pdf(pdf_bytes, content_type)
    if report_date != expected_date:
        raise DownloadError(
            "El parte publicado no corresponde a la fecha esperada: "
            f"esperado {expected_date.isoformat()}, "
            f"encontrado {report_date.isoformat()}."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_entries = load_manifest(manifest_path)
    sha256 = calculate_sha256(pdf_bytes)

    for entry in manifest_entries:
        if entry.get("sha256") == sha256:
            existing_path = output_dir / str(entry.get("filename", ""))
            if existing_path.is_file():
                return ArchiveResult(
                    status="unchanged",
                    path=existing_path,
                    report_date=report_date,
                    sha256=sha256,
                )

    canonical_path = (
        output_dir / f"ActuacionesMITECO-definitivo-{report_date.isoformat()}.pdf"
    )
    same_date_entries = [
        entry
        for entry in manifest_entries
        if entry.get("report_date") == report_date.isoformat()
    ]
    previous_sha256 = (
        str(same_date_entries[-1].get("sha256"))
        if same_date_entries
        else None
    )

    existing_same_content = find_existing_pdf_by_hash(output_dir, sha256)
    if existing_same_content is not None:
        destination_path = existing_same_content
        status = "registered"
    else:
        previous_filename = (
            str(same_date_entries[-1].get("filename", ""))
            if same_date_entries
            else ""
        )
        previous_path = output_dir / previous_filename
        destination_path = (
            previous_path if previous_filename and previous_path.is_file()
            else canonical_path
        )
        destination_path.write_bytes(pdf_bytes)
        status = "revised" if previous_sha256 is not None else "downloaded"

    timestamp = downloaded_at or datetime.now(MADRID_TIMEZONE)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=MADRID_TIMEZONE)

    manifest_entry = ManifestEntry(
        report_date=report_date.isoformat(),
        downloaded_at=timestamp.isoformat(),
        source_page_url=SOURCE_PAGE_URL,
        source_pdf_url=report_link.url,
        source_title=report_link.title,
        sha256=sha256,
        filename=destination_path.name,
        content_length=len(pdf_bytes),
        previous_sha256=previous_sha256,
    )
    append_manifest_entry(manifest_path, manifest_entry)

    return ArchiveResult(
        status=status,
        path=destination_path,
        report_date=report_date,
        sha256=sha256,
    )


def expected_previous_day(now: datetime | None = None) -> date:
    """Devuelve el dia anterior segun la zona horaria de Madrid."""

    current_time = now or datetime.now(MADRID_TIMEZONE)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=MADRID_TIMEZONE)
    return current_time.astimezone(MADRID_TIMEZONE).date() - timedelta(days=1)


def parse_iso_date(value: str) -> date:
    """Convierte un argumento YYYY-MM-DD en ``date``."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "La fecha debe utilizar el formato YYYY-MM-DD."
        ) from error


def build_argument_parser() -> argparse.ArgumentParser:
    """Construye la interfaz de linea de comandos."""

    parser = argparse.ArgumentParser(
        description="Descarga el parte definitivo diario de MITECO."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directorio de salida (por defecto: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--expected-date",
        type=parse_iso_date,
        default=None,
        help=(
            "Fecha que debe contener el parte, en formato YYYY-MM-DD. "
            "Por defecto se exige el dia anterior en Europe/Madrid."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la descarga y devuelve un codigo apto para automatizacion."""

    arguments = build_argument_parser().parse_args(argv)
    expected_date = arguments.expected_date or expected_previous_day()

    try:
        with create_http_client() as client:
            report_link, pdf_bytes, content_type = fetch_report(client)
        result = archive_report(
            pdf_bytes=pdf_bytes,
            content_type=content_type,
            report_link=report_link,
            output_dir=arguments.output_dir,
            expected_date=expected_date,
        )
    except (DownloadError, httpx.HTTPError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": result.status,
                "report_date": result.report_date.isoformat(),
                "path": str(result.path),
                "sha256": result.sha256,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
