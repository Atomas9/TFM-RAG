"""Persistencia SQL de los metadatos de los snapshots de incendios.

El JSONL continúa siendo la fuente de verdad. Esta base SQLite es un artefacto
regenerable para resolver de forma eficiente consultas como mínimos, máximos,
recuentos y evoluciones temporales.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS_PATH = PROJECT_ROOT / "data" / "processed" / "fire_snapshots.jsonl"
METADATA_DB_PATH = PROJECT_ROOT / "data" / "metadata" / "miteco_metadata.sqlite"


# Solo se guardan los campos que necesitaremos para filtrar, agregar y enlazar
# cada fila con el documento equivalente de Chroma mediante ``snapshot_id``.
UPSERT_SNAPSHOT_SQL = """
    INSERT INTO fire_snapshots (
        snapshot_id,
        incident_key,
        report_date_number,
        country,
        autonomous_community_normalized,
        province_normalized,
        location_normalized,
        status,
        operational_status,
        source_file,
        source_sha256
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(snapshot_id) DO UPDATE SET
        incident_key = excluded.incident_key,
        report_date_number = excluded.report_date_number,
        country = excluded.country,
        autonomous_community_normalized =
            excluded.autonomous_community_normalized,
        province_normalized = excluded.province_normalized,
        location_normalized = excluded.location_normalized,
        status = excluded.status,
        operational_status = excluded.operational_status,
        source_file = excluded.source_file,
        source_sha256 = excluded.source_sha256
"""


def connect_metadata_db(
    database_path: Path = METADATA_DB_PATH,
) -> sqlite3.Connection:
    """Abre la base SQLite y crea su directorio si todavía no existe."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Crea la tabla y los índices; puede llamarse más de una vez."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS fire_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            incident_key TEXT NOT NULL,
            report_date_number INTEGER NOT NULL,
            country TEXT NOT NULL,
            autonomous_community_normalized TEXT,
            province_normalized TEXT,
            location_normalized TEXT NOT NULL,
            status TEXT,
            operational_status TEXT,
            source_file TEXT NOT NULL,
            source_sha256 TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_fire_report_date
            ON fire_snapshots(report_date_number);

        CREATE INDEX IF NOT EXISTS idx_fire_province_date
            ON fire_snapshots(province_normalized, report_date_number);

        CREATE INDEX IF NOT EXISTS idx_fire_community_date
            ON fire_snapshots(
                autonomous_community_normalized,
                report_date_number
            );

        CREATE INDEX IF NOT EXISTS idx_fire_location_date
            ON fire_snapshots(location_normalized, report_date_number);

        CREATE INDEX IF NOT EXISTS idx_fire_incident_date
            ON fire_snapshots(incident_key, report_date_number);
        """
    )
    connection.commit()


def load_snapshot_metadata(
    snapshots_path: Path = SNAPSHOTS_PATH,
) -> list[dict[str, object]]:
    """Lee del JSONL los objetos que después se sincronizarán con SQLite."""

    snapshots: list[dict[str, object]] = []

    with snapshots_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                snapshot = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"JSON inválido en la línea {line_number} de "
                    f"{snapshots_path}."
                ) from error

            if not isinstance(snapshot, dict):
                raise ValueError(
                    f"La línea {line_number} de {snapshots_path} "
                    "no contiene un objeto JSON."
                )

            snapshots.append(snapshot)

    return snapshots


def _snapshot_values(snapshot: Mapping[str, object]) -> tuple[object, ...]:
    """Transforma un snapshot en los valores ordenados del INSERT SQL."""

    required_fields = (
        "snapshot_id",
        "incident_key",
        "report_date_number",
        "country",
        "location_normalized",
        "source_file",
        "source_sha256",
    )
    missing_fields = [
        field
        for field in required_fields
        if field not in snapshot or snapshot[field] is None
    ]

    if missing_fields:
        raise ValueError(
            "El snapshot no contiene los campos obligatorios: "
            + ", ".join(missing_fields)
        )

    return (
        snapshot["snapshot_id"],
        snapshot["incident_key"],
        snapshot["report_date_number"],
        snapshot["country"],
        snapshot.get("autonomous_community_normalized"),
        snapshot.get("province_normalized"),
        snapshot["location_normalized"],
        snapshot.get("status"),
        snapshot.get("operational_status"),
        snapshot["source_file"],
        snapshot["source_sha256"],
    )


def sync_snapshots(
    connection: sqlite3.Connection,
    snapshots: Iterable[Mapping[str, object]],
) -> int:
    """Inserta o actualiza snapshots y devuelve cuántos se han procesado."""

    rows = [_snapshot_values(snapshot) for snapshot in snapshots]

    # El contexto agrupa todos los cambios en una única transacción. Si falla
    # una fila, SQLite revierte la sincronización completa.
    with connection:
        connection.executemany(UPSERT_SNAPSHOT_SQL, rows)

    return len(rows)


def count_snapshot_rows(connection: sqlite3.Connection) -> int:
    """Devuelve el número de snapshots almacenados en la tabla."""

    result = connection.execute(
        "SELECT COUNT(*) AS total FROM fire_snapshots"
    ).fetchone()
    return int(result["total"])


def build_metadata_database(
    snapshots_path: Path = SNAPSHOTS_PATH,
    database_path: Path = METADATA_DB_PATH,
) -> tuple[int, int]:
    """Crea o actualiza la base y devuelve procesados y total almacenado."""

    snapshots = load_snapshot_metadata(snapshots_path)
    connection = connect_metadata_db(database_path)

    try:
        create_schema(connection)
        processed = sync_snapshots(connection, snapshots)
        total = count_snapshot_rows(connection)
    finally:
        connection.close()

    return processed, total


def main() -> None:
    """Construye la base local desde el JSONL procesado del proyecto."""

    processed, total = build_metadata_database()
    print(f"Snapshots procesados: {processed}")
    print(f"Registros en SQLite: {total}")
    print(f"Base de metadatos: {METADATA_DB_PATH.resolve()}")


if __name__ == "__main__":
    main()
