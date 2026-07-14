from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import fitz  # PyMuPDF
import httpx
from bs4 import BeautifulSoup


MITECO_ACTUACIONES_URL = (
    "https://www.miteco.gob.es/es/biodiversidad/temas/"
    "incendios-forestales/estadisticas-actuaciones.html"
)

OUTPUT_DIR = Path("data/miteco")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MitecoReport:
    report_type: str  # "definitivo" | "provisional"
    title: str
    source_url: str
    local_pdf_path: str
    local_text_path: str
    sha256: str
    fetched_at: str
    text: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalize_filename(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9áéíóúñü_-]+", "_", text)
    text = text.strip("_")
    return text[:120]


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "TFM-RAG-Incendios/1.0 contacto: ejemplo@universidad.es"
    }

    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def find_miteco_report_links() -> dict[str, dict[str, str]]:
    """
    Devuelve los enlaces al parte definitivo y provisional de MITECO.

    Resultado:
    {
        "definitivo": {
            "title": "...",
            "url": "https://..."
        },
        "provisional": {
            "title": "...",
            "url": "https://..."
        }
    }
    """
    html = fetch_html(MITECO_ACTUACIONES_URL)
    soup = BeautifulSoup(html, "html.parser")

    reports: dict[str, dict[str, str]] = {}

    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        title_lower = title.lower()
        href = urljoin(MITECO_ACTUACIONES_URL, a["href"])

        if "parte definitivo" in title_lower:
            reports["definitivo"] = {
                "title": title,
                "url": href,
            }

        elif "parte provisional" in title_lower:
            reports["provisional"] = {
                "title": title,
                "url": href,
            }

    missing = {"definitivo", "provisional"} - set(reports.keys())
    if missing:
        raise RuntimeError(f"No se encontraron estos partes en MITECO: {missing}")

    return reports


def download_pdf(url: str) -> bytes:
    headers = {
        "User-Agent": "TFM-RAG-Incendios/1.0 contacto: ejemplo@universidad.es",
        "Accept": "application/pdf,*/*",
    }

    with httpx.Client(timeout=60, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
            raise ValueError(
                f"La URL no parece devolver un PDF. "
                f"Content-Type={content_type}, url={url}"
            )

        return response.content


def extract_text_from_pdf(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    pages_text: list[str] = []

    for page_index, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages_text.append(f"\n\n--- Página {page_index} ---\n{text}")

    return "\n".join(pages_text).strip()


def load_seen_hashes(index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()

    with index_path.open("r", encoding="utf-8") as f:
        records = json.load(f)

    return {record["sha256"] for record in records}


def append_to_index(index_path: Path, report: MitecoReport) -> None:
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []

    records.append(asdict(report))

    with index_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def download_and_extract_report(
    report_type: str,
    title: str,
    url: str,
    skip_if_seen: bool = True,
) -> Optional[MitecoReport]:
    index_path = OUTPUT_DIR / "index.json"
    seen_hashes = load_seen_hashes(index_path)

    pdf_bytes = download_pdf(url)
    digest = sha256_bytes(pdf_bytes)

    if skip_if_seen and digest in seen_hashes:
        print(f"[{report_type}] Sin cambios. Hash ya procesado: {digest}")
        return None

    fetched_at = datetime.now(timezone.utc).isoformat()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    safe_title = normalize_filename(title or report_type)

    pdf_path = OUTPUT_DIR / f"{timestamp}_{report_type}_{safe_title}_{digest[:12]}.pdf"
    text_path = OUTPUT_DIR / f"{timestamp}_{report_type}_{safe_title}_{digest[:12]}.txt"

    pdf_path.write_bytes(pdf_bytes)

    text = extract_text_from_pdf(pdf_path)
    text_path.write_text(text, encoding="utf-8")

    report = MitecoReport(
        report_type=report_type,
        title=title,
        source_url=url,
        local_pdf_path=str(pdf_path),
        local_text_path=str(text_path),
        sha256=digest,
        fetched_at=fetched_at,
        text=text,
    )

    append_to_index(index_path, report)

    print(f"[{report_type}] Descargado y extraído:")
    print(f"  PDF:  {pdf_path}")
    print(f"  TXT:  {text_path}")
    print(f"  HASH: {digest}")

    return report


def main() -> list[MitecoReport]:
    links = find_miteco_report_links()

    extracted_reports: list[MitecoReport] = []

    for report_type in ["definitivo", "provisional"]:
        item = links[report_type]

        report = download_and_extract_report(
            report_type=report_type,
            title=item["title"],
            url=item["url"],
            skip_if_seen=True,
        )

        if report is not None:
            extracted_reports.append(report)

    return extracted_reports


if __name__ == "__main__":
    reports = main()

    print("\nResumen:")
    for report in reports:
        print(f"- {report.report_type}: {report.title}")
        print(f"  URL: {report.source_url}")
        print(f"  Texto extraído: {len(report.text)} caracteres")