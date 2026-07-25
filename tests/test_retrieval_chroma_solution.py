"""Pruebas de integracion interna sin cargar BGE-M3 ni abrir Chroma."""

import numpy as np
import pytest

from miteco_rag.extras.retrieval_chroma_solution import (
    retrieve,
    retrieve_with_filters,
)


SAMPLE_METADATA = {
    "country": "ES",
    "autonomous_community": "Castilla y León",
    "autonomous_community_normalized": "castilla y leon",
    "province": "León",
    "province_normalized": "leon",
    "location": "VILLABLINO",
    "location_normalized": "villablino",
    "status": "ACTIVO",
    "operational_status": "1",
    "report_date_number": 20260712,
}


class FakeModel:
    def __init__(self) -> None:
        self.encoded_queries: list[tuple[str, bool]] = []

    def encode(self, query: str, normalize_embeddings: bool) -> np.ndarray:
        self.encoded_queries.append((query, normalize_embeddings))
        return np.array([0.25, 0.75], dtype=np.float32)


class FakeCollection:
    def __init__(self) -> None:
        self.query_arguments: dict | None = None

    def get(self, include: list[str]) -> dict:
        assert include == ["metadatas"]
        return {"metadatas": [SAMPLE_METADATA]}

    def query(self, **arguments) -> dict:
        self.query_arguments = arguments
        return {
            "ids": [["snapshot-1"]],
            "documents": [["chunk"]],
            "metadatas": [[SAMPLE_METADATA]],
            "distances": [[0.4]],
        }


def test_retrieve_passes_embedding_and_where_to_collection() -> None:
    collection = FakeCollection()
    model = FakeModel()
    where = {"province_normalized": "leon"}

    result = retrieve(
        "incendios en Leon",
        top_k=5,
        where=where,
        db_collection=collection,
        model=model,
    )

    assert result["ids"] == [["snapshot-1"]]
    assert model.encoded_queries == [("incendios en Leon", True)]
    assert collection.query_arguments == {
        "query_embeddings": [[0.25, 0.75]],
        "n_results": 5,
        "include": ["documents", "metadatas", "distances"],
        "where": where,
    }


def test_retrieve_without_filters_omits_where_argument() -> None:
    collection = FakeCollection()

    retrieve(
        "gran despliegue aereo",
        db_collection=collection,
        model=FakeModel(),
    )

    assert collection.query_arguments is not None
    assert "where" not in collection.query_arguments


def test_retrieve_with_filters_returns_auditable_interpretation() -> None:
    collection = FakeCollection()

    results, parsed_query, where = retrieve_with_filters(
        "Incendios activos en Leon",
        top_k=3,
        db_collection=collection,
        model=FakeModel(),
    )

    assert results["ids"] == [["snapshot-1"]]
    assert parsed_query.filters.included_provinces == ["leon"]
    assert parsed_query.filters.included_statuses == ["ACTIVO"]
    assert where == {
        "$and": [
            {"province_normalized": "leon"},
            {"status": "ACTIVO"},
            {"report_date_number": 20260712},
        ]
    }


def test_retrieve_with_filters_stops_on_contradiction() -> None:
    collection = FakeCollection()

    with pytest.raises(ValueError, match="Consulta ambigua"):
        retrieve_with_filters(
            "Incendios de Leon, pero no de Leon",
            db_collection=collection,
            model=FakeModel(),
        )

    assert collection.query_arguments is None
