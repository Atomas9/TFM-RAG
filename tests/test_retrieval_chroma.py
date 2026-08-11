"""Pruebas de los retrievals sin cargar BGE-M3 ni una colección real."""

from collections.abc import Iterator
from pathlib import Path
import sqlite3

import numpy as np
import pytest

from miteco_rag.metadata_store import (
    connect_metadata_db,
    create_schema,
    sync_snapshots,
)
from miteco_rag.retrieval_chroma import (
    retrieve,
    retrieve_count,
    retrieve_min_max,
)


class FakeModel:
    """Modelo mínimo que registra la pregunta recibida."""

    def __init__(self) -> None:
        self.encoded_queries: list[tuple[str, bool]] = []

    def encode(self, query: str, normalize_embeddings: bool) -> np.ndarray:
        self.encoded_queries.append((query, normalize_embeddings))
        return np.array([0.25, 0.75], dtype=np.float32)


class FakeCollection:
    """Colección Chroma simulada para query y get."""

    def __init__(self) -> None:
        self.query_arguments: dict[str, object] | None = None
        self.get_arguments: dict[str, object] | None = None

    def query(self, **arguments):
        self.query_arguments = arguments
        return {
            "ids": [["hybrid-1"]],
            "documents": [["Documento semántico"]],
            "metadatas": [[{"province_normalized": "leon"}]],
            "distances": [[0.3]],
        }

    def get(self, **arguments):
        self.get_arguments = arguments
        ids = arguments["ids"]
        return {
            "ids": ids,
            "documents": [f"Documento {snapshot_id}" for snapshot_id in ids],
            "metadatas": [
                {"snapshot_id": snapshot_id}
                for snapshot_id in ids
            ],
        }


def make_snapshot(
    snapshot_id: str,
    report_date_number: int,
    province: str,
    incident_key: str | None = None,
    source_sha256: str | None = None,
) -> dict[str, object]:
    """Crea un snapshot mínimo para la base temporal."""

    return {
        "snapshot_id": snapshot_id,
        "incident_key": incident_key or f"incident-{snapshot_id}",
        "report_date_number": report_date_number,
        "country": "ES",
        "autonomous_community_normalized": "castilla y leon",
        "province_normalized": province,
        "location_normalized": f"location-{snapshot_id}",
        "status": "ACTIVO",
        "operational_status": "1",
        "source_file": f"parte-{report_date_number}.pdf",
        "source_sha256": source_sha256 or f"sha-{snapshot_id}",
    }


@pytest.fixture
def metadata_connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Crea datos donde la fecha global supera la última fecha de León."""

    connection = connect_metadata_db(tmp_path / "metadata.sqlite")
    create_schema(connection)
    sync_snapshots(
        connection,
        [
            make_snapshot(
                "leon-old",
                20260712,
                "leon",
                incident_key="incident-a",
                source_sha256="report-12",
            ),
            make_snapshot(
                "leon-1",
                20260713,
                "leon",
                incident_key="incident-a",
                source_sha256="report-13",
            ),
            make_snapshot(
                "leon-2",
                20260713,
                "leon",
                incident_key="incident-b",
                source_sha256="report-13",
            ),
            make_snapshot("huelva-1", 20260801, "huelva"),
        ],
    )

    yield connection
    connection.close()


def test_hybrid_retrieve_returns_common_flat_format() -> None:
    model = FakeModel()
    collection = FakeCollection()

    result = retrieve(
        query="Incendios en León",
        model=model,
        collection=collection,
        where={"province_normalized": "leon"},
        top_k=5,
    )

    assert result == {
        "mode": "hybrid",
        "ids": ["hybrid-1"],
        "documents": ["Documento semántico"],
        "metadatas": [{"province_normalized": "leon"}],
        "distances": [0.3],
        "aggregate": None,
    }
    assert model.encoded_queries == [("Incendios en León", True)]
    assert collection.query_arguments == {
        "query_embeddings": [[0.25, 0.75]],
        "n_results": 5,
        "include": ["documents", "metadatas", "distances"],
        "where": {"province_normalized": "leon"},
    }


def test_min_max_retrieve_filters_before_selecting_date(
    metadata_connection: sqlite3.Connection,
) -> None:
    collection = FakeCollection()

    result = retrieve_min_max(
        collection=collection,
        metadata_connection=metadata_connection,
        where={"province_normalized": "leon"},
        operation="max",
    )

    assert result == {
        "mode": "min_max",
        "ids": ["leon-1", "leon-2"],
        "documents": ["Documento leon-1", "Documento leon-2"],
        "metadatas": [
            {"snapshot_id": "leon-1"},
            {"snapshot_id": "leon-2"},
        ],
        "distances": None,
        "aggregate": {
            "operation": "max",
            "report_date_number": 20260713,
        },
    }
    assert collection.get_arguments == {
        "ids": ["leon-1", "leon-2"],
        "include": ["documents", "metadatas"],
    }


def test_min_max_retrieve_without_matches_does_not_query_chroma(
    metadata_connection: sqlite3.Connection,
) -> None:
    collection = FakeCollection()

    result = retrieve_min_max(
        collection=collection,
        metadata_connection=metadata_connection,
        where={"province_normalized": "asturias"},
        operation="max",
    )

    assert result == {
        "mode": "min_max",
        "ids": [],
        "documents": [],
        "metadatas": [],
        "distances": None,
        "aggregate": None,
    }
    assert collection.get_arguments is None


@pytest.mark.parametrize(
    ("count_target", "expected"),
    [
        ("incidents", 2),
        ("snapshots", 3),
        ("reports", 2),
    ],
)
def test_retrieve_count_uses_common_contract(
    metadata_connection: sqlite3.Connection,
    count_target: str,
    expected: int,
) -> None:
    result = retrieve_count(
        metadata_connection=metadata_connection,
        where={"province_normalized": "leon"},
        count_target=count_target,  # type: ignore[arg-type]
    )

    assert result == {
        "mode": "count",
        "ids": [],
        "documents": [],
        "metadatas": [],
        "distances": None,
        "aggregate": {
            "count_target": count_target,
            "value": expected,
        },
    }


def test_retrieve_count_preserves_exact_zero(
    metadata_connection: sqlite3.Connection,
) -> None:
    result = retrieve_count(
        metadata_connection=metadata_connection,
        where={"province_normalized": "asturias"},
        count_target="incidents",
    )

    assert result["aggregate"] == {
        "count_target": "incidents",
        "value": 0,
    }
