"""Pruebas de la base SQLite de metadatos sin usar los datos locales."""

import json
from pathlib import Path

import pytest

from miteco_rag.metadata_store import (
    build_metadata_database,
    connect_metadata_db,
    count_snapshot_rows,
    create_schema,
    sync_snapshots,
)


def make_snapshot(
    snapshot_id: str = "snapshot-1",
    *,
    status: str = "ACTIVO",
) -> dict[str, object]:
    """Crea el mínimo snapshot válido necesario para estas pruebas."""

    return {
        "snapshot_id": snapshot_id,
        "incident_key": "incident-villablino",
        "report_date_number": 20260712,
        "country": "ES",
        "autonomous_community_normalized": "castilla y leon",
        "province_normalized": "leon",
        "location_normalized": "villablino",
        "status": status,
        "operational_status": "1",
        "source_file": "parte-2026-07-12.pdf",
        "source_sha256": "abc123",
    }


def write_jsonl(path: Path, snapshots: list[dict[str, object]]) -> None:
    """Escribe snapshots en el formato de una entrada JSON por línea."""

    path.write_text(
        "\n".join(
            json.dumps(snapshot, ensure_ascii=False)
            for snapshot in snapshots
        )
        + "\n",
        encoding="utf-8",
    )


def test_build_database_creates_and_loads_rows(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "fire_snapshots.jsonl"
    database_path = tmp_path / "metadata" / "miteco.sqlite"
    write_jsonl(
        jsonl_path,
        [make_snapshot(), make_snapshot("snapshot-2")],
    )

    processed, total = build_metadata_database(jsonl_path, database_path)

    assert processed == 2
    assert total == 2
    assert database_path.is_file()

    connection = connect_metadata_db(database_path)
    try:
        row = connection.execute(
            """
            SELECT province_normalized, status, report_date_number
            FROM fire_snapshots
            WHERE snapshot_id = ?
            """,
            ("snapshot-1",),
        ).fetchone()
    finally:
        connection.close()

    assert dict(row) == {
        "province_normalized": "leon",
        "status": "ACTIVO",
        "report_date_number": 20260712,
    }


def test_second_sync_updates_without_duplicating(tmp_path: Path) -> None:
    database_path = tmp_path / "miteco.sqlite"
    connection = connect_metadata_db(database_path)

    try:
        create_schema(connection)
        sync_snapshots(connection, [make_snapshot(status="ACTIVO")])
        sync_snapshots(connection, [make_snapshot(status="CONTROLADO")])

        stored_status = connection.execute(
            "SELECT status FROM fire_snapshots WHERE snapshot_id = ?",
            ("snapshot-1",),
        ).fetchone()["status"]

        assert count_snapshot_rows(connection) == 1
        assert stored_status == "CONTROLADO"
    finally:
        connection.close()


def test_schema_creates_query_indexes(tmp_path: Path) -> None:
    connection = connect_metadata_db(tmp_path / "miteco.sqlite")

    try:
        create_schema(connection)
        indexes = {
            row["name"]
            for row in connection.execute(
                "PRAGMA index_list('fire_snapshots')"
            ).fetchall()
        }
    finally:
        connection.close()

    assert {
        "idx_fire_report_date",
        "idx_fire_province_date",
        "idx_fire_community_date",
        "idx_fire_location_date",
        "idx_fire_incident_date",
    }.issubset(indexes)


def test_missing_required_field_does_not_insert_rows(tmp_path: Path) -> None:
    connection = connect_metadata_db(tmp_path / "miteco.sqlite")
    invalid_snapshot = make_snapshot()
    del invalid_snapshot["incident_key"]

    try:
        create_schema(connection)

        with pytest.raises(ValueError, match="incident_key"):
            sync_snapshots(
                connection,
                [make_snapshot(), invalid_snapshot],
            )

        assert count_snapshot_rows(connection) == 0
    finally:
        connection.close()


def test_invalid_json_reports_its_line(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "fire_snapshots.jsonl"
    jsonl_path.write_text(
        json.dumps(make_snapshot()) + "\n{not-json}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="línea 2"):
        build_metadata_database(
            jsonl_path,
            tmp_path / "miteco.sqlite",
        )
