"""Pruebas del compilador de filtros Chroma a SQL parametrizado."""

import pytest

from miteco_rag.metadata_queries import compile_where_to_sql


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
