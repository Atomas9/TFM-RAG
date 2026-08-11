"""Pruebas del selector determinista del modo de recuperacion."""

import pytest

from miteco_rag.retrieval_mode import choose_retrieval_mode


@pytest.mark.parametrize(
    "query",
    [
        "¿Cuál es la primera fecha de la que tienes registro?",
        "¿Desde qué fecha hay informes?",
        "Muéstrame el parte más antiguo",
    ],
)
def test_choose_minimum_query(query: str) -> None:
    result = choose_retrieval_mode(query)

    assert result.mode == "min_max"
    assert result.operation == "min"


@pytest.mark.parametrize(
    "query",
    [
        "¿Cuál es la última fecha registrada?",
        "¿Hasta qué fecha tienes informes?",
        "Muéstrame el incendio más reciente de León",
    ],
)
def test_choose_maximum_query(query: str) -> None:
    result = choose_retrieval_mode(query)

    assert result.mode == "min_max"
    assert result.operation == "max"


@pytest.mark.parametrize(
    "query",
    [
        "¿Cuántos incendios activos hay en León?",
        "Dime el número total de registros",
    ],
)
def test_choose_count_query(query: str) -> None:
    assert choose_retrieval_mode(query).mode == "count"


@pytest.mark.parametrize(
    "query",
    [
        "¿Cómo ha evolucionado el incendio de Villablino?",
        "Dame la cronología del fuego de Orés",
    ],
)
def test_choose_timeline_query(query: str) -> None:
    assert choose_retrieval_mode(query).mode == "timeline"


def test_ordinary_query_uses_hybrid_search() -> None:
    result = choose_retrieval_mode("¿Qué incendios activos hay en León?")

    assert result.mode == "hybrid"
    assert result.operation is None


def test_empty_query_is_rejected() -> None:
    with pytest.raises(ValueError, match="vacia"):
        choose_retrieval_mode("   ")
