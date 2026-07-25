"""Pruebas sin red para el descargador diario de MITECO."""

from datetime import date, datetime
import json
from pathlib import Path

import pymupdf
import pytest

from miteco_rag.download_miteco_report import (
    DownloadError,
    MANIFEST_FILENAME,
    ReportLink,
    archive_report,
    extract_report_date,
    find_definitive_report_link,
    validate_pdf,
)


def make_report_pdf(
    report_date_text: str = "viernes, 24 de julio de 2026",
    extra_text: str = "",
) -> bytes:
    """Crea en memoria un PDF minimo con el encabezado esperado."""

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "INTERVENCIONES DE MEDIOS DEL MINISTERIO PARA APOYAR EN LA\n"
            "EXTINCION DE INCENDIOS FORESTALES\n"
            f"{report_date_text}\n"
            f"{extra_text}"
        ),
    )
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def read_manifest(output_dir: Path) -> list[dict[str, object]]:
    manifest_path = output_dir / MANIFEST_FILENAME
    return [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
    ]


def test_find_definitive_report_link_resolves_relative_url() -> None:
    html = """
    <html><body>
      <a href="/documentos/parte.pdf">
        Parte Definitivo de Intervenciones (día previo)
      </a>
    </body></html>
    """

    result = find_definitive_report_link(
        html,
        "https://www.miteco.gob.es/es/pagina.html",
    )

    assert result.title == "Parte Definitivo de Intervenciones (día previo)"
    assert result.url == "https://www.miteco.gob.es/documentos/parte.pdf"


def test_find_definitive_report_link_fails_if_link_is_missing() -> None:
    with pytest.raises(DownloadError, match="No se encontro"):
        find_definitive_report_link("<a href='otro.pdf'>Otro documento</a>")


def test_extract_report_date_from_pdf() -> None:
    assert extract_report_date(make_report_pdf()) == date(2026, 7, 24)


@pytest.mark.parametrize(
    ("pdf_bytes", "content_type", "message"),
    [
        (b"not a pdf", "application/pdf", "firma"),
        (make_report_pdf(), "text/html", "tipo de contenido"),
    ],
)
def test_validate_pdf_rejects_invalid_response(
    pdf_bytes: bytes,
    content_type: str,
    message: str,
) -> None:
    with pytest.raises(DownloadError, match=message):
        validate_pdf(pdf_bytes, content_type)


def test_archive_new_report_and_write_manifest(tmp_path: Path) -> None:
    report_link = ReportLink("Parte definitivo", "https://example.test/report.pdf")
    pdf_bytes = make_report_pdf()

    result = archive_report(
        pdf_bytes=pdf_bytes,
        content_type="application/pdf",
        report_link=report_link,
        output_dir=tmp_path,
        expected_date=date(2026, 7, 24),
        downloaded_at=datetime.fromisoformat("2026-07-25T12:00:00+02:00"),
    )

    assert result.status == "downloaded"
    assert result.path.name == "ActuacionesMITECO-definitivo-2026-07-24.pdf"
    assert result.path.read_bytes() == pdf_bytes
    manifest = read_manifest(tmp_path)
    assert len(manifest) == 1
    assert manifest[0]["report_date"] == "2026-07-24"
    assert manifest[0]["filename"] == result.path.name
    assert manifest[0]["previous_sha256"] is None


def test_archive_same_hash_is_idempotent(tmp_path: Path) -> None:
    report_link = ReportLink("Parte definitivo", "https://example.test/report.pdf")
    pdf_bytes = make_report_pdf()
    arguments = {
        "pdf_bytes": pdf_bytes,
        "content_type": "application/pdf",
        "report_link": report_link,
        "output_dir": tmp_path,
        "expected_date": date(2026, 7, 24),
    }

    archive_report(**arguments)
    result = archive_report(**arguments)

    assert result.status == "unchanged"
    assert len(read_manifest(tmp_path)) == 1
    assert len(list(tmp_path.glob("*.pdf"))) == 1


def test_archive_revision_replaces_daily_file_and_records_previous_hash(
    tmp_path: Path,
) -> None:
    report_link = ReportLink("Parte definitivo", "https://example.test/report.pdf")
    first_pdf = make_report_pdf(extra_text="Primera version")
    revised_pdf = make_report_pdf(extra_text="Version corregida")

    first_result = archive_report(
        pdf_bytes=first_pdf,
        content_type="application/pdf",
        report_link=report_link,
        output_dir=tmp_path,
        expected_date=date(2026, 7, 24),
    )
    revised_result = archive_report(
        pdf_bytes=revised_pdf,
        content_type="application/pdf",
        report_link=report_link,
        output_dir=tmp_path,
        expected_date=date(2026, 7, 24),
    )

    assert revised_result.status == "revised"
    assert revised_result.path.read_bytes() == revised_pdf
    manifest = read_manifest(tmp_path)
    assert len(manifest) == 2
    assert manifest[-1]["previous_sha256"] == first_result.sha256


def test_archive_rejects_stale_report(tmp_path: Path) -> None:
    with pytest.raises(DownloadError, match="no corresponde"):
        archive_report(
            pdf_bytes=make_report_pdf(),
            content_type="application/pdf",
            report_link=ReportLink("Parte", "https://example.test/report.pdf"),
            output_dir=tmp_path,
            expected_date=date(2026, 7, 23),
        )

    assert not tmp_path.exists() or not any(tmp_path.iterdir())


def test_existing_legacy_pdf_is_registered_without_duplicate(tmp_path: Path) -> None:
    pdf_bytes = make_report_pdf()
    legacy_path = tmp_path / "ActuacionesMITECO-definitivo24072026.pdf"
    legacy_path.write_bytes(pdf_bytes)

    result = archive_report(
        pdf_bytes=pdf_bytes,
        content_type="application/pdf",
        report_link=ReportLink("Parte", "https://example.test/report.pdf"),
        output_dir=tmp_path,
        expected_date=date(2026, 7, 24),
    )

    assert result.status == "registered"
    assert result.path == legacy_path
    assert len(list(tmp_path.glob("*.pdf"))) == 1
    assert read_manifest(tmp_path)[0]["filename"] == legacy_path.name


def test_revision_overwrites_registered_legacy_file(tmp_path: Path) -> None:
    first_pdf = make_report_pdf(extra_text="Primera version")
    revised_pdf = make_report_pdf(extra_text="Version revisada")
    legacy_path = tmp_path / "ActuacionesMITECO-definitivo24072026.pdf"
    legacy_path.write_bytes(first_pdf)
    report_link = ReportLink("Parte", "https://example.test/report.pdf")

    archive_report(
        pdf_bytes=first_pdf,
        content_type="application/pdf",
        report_link=report_link,
        output_dir=tmp_path,
        expected_date=date(2026, 7, 24),
    )
    result = archive_report(
        pdf_bytes=revised_pdf,
        content_type="application/pdf",
        report_link=report_link,
        output_dir=tmp_path,
        expected_date=date(2026, 7, 24),
    )

    assert result.status == "revised"
    assert result.path == legacy_path
    assert legacy_path.read_bytes() == revised_pdf
    assert len(list(tmp_path.glob("*.pdf"))) == 1
