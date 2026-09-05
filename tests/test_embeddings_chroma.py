"""Pruebas de la selección incremental sin cargar BGE-M3 ni abrir Chroma."""

from dataclasses import dataclass

from miteco_rag import embeddings_chroma


@dataclass
class FakeSnapshot:
    snapshot_id: str
    chunk_text: str

    def model_dump(self, mode: str) -> dict[str, str]:
        assert mode == "json"
        return {
            "snapshot_id": self.snapshot_id,
            "chunk_text": self.chunk_text,
        }


class FakeCollection:
    def __init__(self, ids, metadatas) -> None:
        self.ids = ids
        self.metadatas = metadatas

    def get(self, include):
        assert include == ["metadatas"]
        return {
            "ids": self.ids,
            "metadatas": self.metadatas,
        }

    def count(self) -> int:
        return len(self.ids)


def test_index_signature_changes_when_content_changes() -> None:
    original = FakeSnapshot("snapshot-1", "Contenido original")
    modified = FakeSnapshot("snapshot-1", "Contenido modificado")

    assert (
        embeddings_chroma.build_index_signature(original)
        != embeddings_chroma.build_index_signature(modified)
    )


def test_load_existing_signatures() -> None:
    collection = FakeCollection(
        ids=["snapshot-1", "snapshot-2"],
        metadatas=[
            {"index_signature": "firma-1"},
            {"index_signature": "firma-2"},
        ],
    )

    assert embeddings_chroma.load_existing_signatures(collection) == {
        "snapshot-1": "firma-1",
        "snapshot-2": "firma-2",
    }


def test_selects_only_new_or_modified_snapshots() -> None:
    unchanged = FakeSnapshot("snapshot-1", "Sin cambios")
    modified = FakeSnapshot("snapshot-2", "Contenido nuevo")
    new = FakeSnapshot("snapshot-3", "Snapshot nuevo")
    previous_modified = FakeSnapshot("snapshot-2", "Contenido anterior")

    existing_signatures = {
        "snapshot-1": embeddings_chroma.build_index_signature(unchanged),
        "snapshot-2": embeddings_chroma.build_index_signature(
            previous_modified
        ),
    }

    selected = embeddings_chroma.select_snapshots_to_index(
        [unchanged, modified, new],
        existing_signatures,
    )

    assert selected == [modified, new]


def test_record_without_signature_is_selected_for_migration() -> None:
    snapshot = FakeSnapshot("snapshot-1", "Contenido")

    selected = embeddings_chroma.select_snapshots_to_index(
        [snapshot],
        {"snapshot-1": None},
    )

    assert selected == [snapshot]


def test_main_does_not_load_model_when_index_is_current(
    monkeypatch,
    capsys,
) -> None:
    snapshot = FakeSnapshot("snapshot-1", "Contenido")
    signature = embeddings_chroma.build_index_signature(snapshot)
    collection = FakeCollection(
        ids=[snapshot.snapshot_id],
        metadatas=[{"index_signature": signature}],
    )

    class FakeClient:
        def get_or_create_collection(self, **arguments):
            return collection

    monkeypatch.setattr(
        embeddings_chroma,
        "load_snapshots",
        lambda path: [snapshot],
    )
    monkeypatch.setattr(
        embeddings_chroma.chromadb,
        "PersistentClient",
        lambda path: FakeClient(),
    )

    def fail_if_model_loads(*arguments, **keywords):
        raise AssertionError("BGE-M3 no debería cargarse")

    monkeypatch.setattr(
        embeddings_chroma,
        "SentenceTransformer",
        fail_if_model_loads,
    )

    embeddings_chroma.main()

    output = capsys.readouterr().out
    assert "Snapshots pendientes: 0" in output
    assert "No se carga el modelo de embeddings" in output
