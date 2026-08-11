"""Pruebas del compilador de filtros Chroma a SQL parametrizado."""

from collections.abc import Iterator
from pathlib import Path
import sqlite3

import pytest

from miteco_rag.metadata_queries import (
    compile_where_to_sql,
    count_matches,
    get_extreme_report_date,
    get_extreme_snapshot_ids,
    get_snapshot_ids_for_report_date,
)
from miteco_rag.metadata_store import (
    connect_metadata_db,
    create_schema,
    sync_snapshots,
)


def make_snapshot(
    snapshot_id: str,
    report_date_number: int,
    province: str,
    status: str = "ACTIVO",
    incident_key: str | None = None,
    source_sha256: str | None = None,
) -> dict[str, object]:
    """Crea un snapshot mínimo para probar consultas SQL."""

    return {
        "snapshot_id": snapshot_id,
        "incident_key": incident_key or f"incident-{snapshot_id}",
        "report_date_number": report_date_number,
        "country": "ES",
        "autonomous_community_normalized": "castilla y leon",
        "province_normalized": province,
        "location_normalized": f"location-{snapshot_id}",
        "status": status,
        "operational_status": "1",
        "source_file": f"parte-{report_date_number}.pdf",
        "source_sha256": source_sha256 or f"sha-{snapshot_id}",
    }


@pytest.fixture
def metadata_connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Crea una base temporal con fechas y provincias diferentes."""

    connection = connect_metadata_db(tmp_path / "metadata.sqlite")
    create_schema(connection)
    sync_snapshots(
        connection,
        [
            make_snapshot(
                "1",
                20260701,
                "leon",
                incident_key="incident-a",
                source_sha256="report-1",
            ),
            make_snapshot(
                "2",
                20260715,
                "leon",
                "CONTROLADO",
                incident_key="incident-a",
                source_sha256="report-2",
            ),
            make_snapshot(
                "5",
                20260715,
                "leon",
                incident_key="incident-b",
                source_sha256="report-2",
            ),
            make_snapshot("3", 20260720, "palencia"),
            make_snapshot("4", 20260801, "huelva"),
        ],
    )

    yield connection
    connection.close()


def test_none_where_produces_no_sql_filter() -> None:
    assert compile_where_to_sql(None) == ("", [])


def test_simple_equality() -> None:
    sql, parameters = compile_where_to_sql(
        {"province_normalized": "leon"}
    )

    assert sql == "province_normalized = ?"
    assert parameters == ["leon"]


def test_and_group_with_date_range() -> None:
    sql, parameters = compile_where_to_sql(
        {
            "$and": [
                {"status": "ACTIVO"},
                {"report_date_number": {"$gte": 20260701}},
                {"report_date_number": {"$lte": 20260731}},
            ]
        }
    )

    assert sql == (
        "(status = ?) AND "
        "(report_date_number >= ?) AND "
        "(report_date_number <= ?)"
    )
    assert parameters == ["ACTIVO", 20260701, 20260731]


def test_nested_or_group_preserves_parentheses() -> None:
    sql, parameters = compile_where_to_sql(
        {
            "$and": [
                {
                    "$or": [
                        {"province_normalized": "leon"},
                        {
                            "autonomous_community_normalized":
                                "andalucia"
                        },
                    ]
                },
                {"status": {"$ne": "EXTINGUIDO"}},
            ]
        }
    )

    assert sql == (
        "((province_normalized = ?) OR "
        "(autonomous_community_normalized = ?)) AND "
        "(status != ?)"
    )
    assert parameters == ["leon", "andalucia", "EXTINGUIDO"]


@pytest.mark.parametrize(
    ("where", "expected_sql", "expected_parameters"),
    [
        (
            {"province_normalized": {"$in": ["leon", "palencia"]}},
            "province_normalized IN (?, ?)",
            ["leon", "palencia"],
        ),
        (
            {"status": {"$nin": ["EXTINGUIDO", "CONTROLADO"]}},
            "status NOT IN (?, ?)",
            ["EXTINGUIDO", "CONTROLADO"],
        ),
    ],
)
def test_list_operators(
    where: dict[str, object],
    expected_sql: str,
    expected_parameters: list[object],
) -> None:
    assert compile_where_to_sql(where) == (
        expected_sql,
        expected_parameters,
    )


def test_value_is_kept_out_of_sql_text() -> None:
    suspicious_value = "leon' OR 1 = 1 --"

    sql, parameters = compile_where_to_sql(
        {"province_normalized": suspicious_value}
    )

    assert sql == "province_normalized = ?"
    assert suspicious_value not in sql
    assert parameters == [suspicious_value]


@pytest.mark.parametrize(
    ("where", "message"),
    [
        ({"invented_field": "value"}, "Campo SQL no permitido"),
        ({"status": {"$contains": "ACTIVO"}}, "Operador SQL no permitido"),
        ({"status": {"$in": []}}, "lista no vacía"),
        ({"$and": []}, "lista no vacía"),
        ({"status": None}, "valor escalar no nulo"),
        ({"status": ("ACTIVO",)}, "valor escalar no nulo"),
        (
            {"status": "ACTIVO", "country": "ES"},
            "una única clave",
        ),
    ],
)
def test_invalid_filters_are_rejected(
    where: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        compile_where_to_sql(where)


def test_global_minimum_report_date(
    metadata_connection: sqlite3.Connection,
) -> None:
    result = get_extreme_report_date(
        metadata_connection,
        where=None,
        operation="min",
    )

    assert result == 20260701


def test_global_maximum_report_date(
    metadata_connection: sqlite3.Connection,
) -> None:
    result = get_extreme_report_date(
        metadata_connection,
        where=None,
        operation="max",
    )

    assert result == 20260801


def test_filtered_maximum_report_date(
    metadata_connection: sqlite3.Connection,
) -> None:
    result = get_extreme_report_date(
        metadata_connection,
        where={"province_normalized": "leon"},
        operation="max",
    )

    assert result == 20260715


def test_minimum_with_compound_filter(
    metadata_connection: sqlite3.Connection,
) -> None:
    result = get_extreme_report_date(
        metadata_connection,
        where={
            "$and": [
                {
                    "province_normalized": {
                        "$in": ["leon", "palencia"]
                    }
                },
                {"status": "ACTIVO"},
            ]
        },
        operation="min",
    )

    assert result == 20260701


def test_extreme_date_returns_none_without_matches(
    metadata_connection: sqlite3.Connection,
) -> None:
    result = get_extreme_report_date(
        metadata_connection,
        where={"province_normalized": "asturias"},
        operation="max",
    )

    assert result is None


def test_invalid_extreme_operation_is_rejected(
    metadata_connection: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="'min' o 'max'"):
        get_extreme_report_date(
            metadata_connection,
            where=None,
            operation="average",  # type: ignore[arg-type]
        )


def test_get_snapshot_ids_for_date_applies_existing_filter(
    metadata_connection: sqlite3.Connection,
) -> None:
    result = get_snapshot_ids_for_report_date(
        metadata_connection,
        where={"status": "ACTIVO"},
        report_date_number=20260715,
    )

    assert result == ["5"]


def test_get_extreme_snapshot_ids_returns_all_tied_records(
    metadata_connection: sqlite3.Connection,
) -> None:
    report_date, snapshot_ids = get_extreme_snapshot_ids(
        metadata_connection,
        where={"province_normalized": "leon"},
        operation="max",
    )

    assert report_date == 20260715
    assert snapshot_ids == ["2", "5"]


def test_get_extreme_snapshot_ids_without_matches(
    metadata_connection: sqlite3.Connection,
) -> None:
    report_date, snapshot_ids = get_extreme_snapshot_ids(
        metadata_connection,
        where={"province_normalized": "asturias"},
        operation="min",
    )

    assert report_date is None
    assert snapshot_ids == []


@pytest.mark.parametrize(
    ("count_target", "expected"),
    [
        ("incidents", 2),
        ("snapshots", 3),
        ("reports", 2),
    ],
)
def test_count_matches_distinguishes_targets(
    metadata_connection: sqlite3.Connection,
    count_target: str,
    expected: int,
) -> None:
    result = count_matches(
        metadata_connection,
        where={"province_normalized": "leon"},
        count_target=count_target,  # type: ignore[arg-type]
    )

    assert result == expected


def test_count_matches_returns_zero_without_matches(
    metadata_connection: sqlite3.Connection,
) -> None:
    result = count_matches(
        metadata_connection,
        where={"province_normalized": "asturias"},
        count_target="incidents",
    )

    assert result == 0


def test_count_matches_rejects_unknown_target(
    metadata_connection: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="objetivo"):
        count_matches(
            metadata_connection,
            where=None,
            count_target="documents",  # type: ignore[arg-type]
        )
