"""Casos de estructura documental del parser de partes MITECO."""

from pathlib import Path

import pytest

from miteco_rag.parseo_y_chuncking import (
    PDFLine,
    create_parser_report,
    normalize_text,
    split_fire_blocks,
)


def make_line(text: str, line_number: int = 1) -> PDFLine:
    return PDFLine(
        page_number=1,
        line_number=line_number,
        raw_text=text,
        cleaned_text=text,
        normalized_text=normalize_text(text),
    )


def test_report_without_fire_operations_returns_no_blocks() -> None:
    lines = [
        make_line(
            "SIN ACTUACIÓN EN INCENDIO DE LOS MEDIOS DEL MINISTERIO"
        ),
        make_line("ACTUACIONES DE LOS MEDIOS DEL MINISTERIO", 2),
        make_line("Nº INCENDIOS", 3),
        make_line("0", 4),
    ]

    assert split_fire_blocks(lines) == []


def test_report_without_blocks_or_empty_marker_still_fails() -> None:
    lines = [make_line("Documento con estructura desconocida")]

    with pytest.raises(
        ValueError,
        match="No se encontraron bloques",
    ):
        split_fire_blocks(lines)


def test_parser_report_includes_processed_file_with_zero_snapshots() -> None:
    report = create_parser_report(
        snapshots=[],
        processed_files=[Path("empty-report.pdf")],
        warnings=[],
        errors=[],
    )

    assert report.snapshots_by_file == {"empty-report.pdf": 0}
