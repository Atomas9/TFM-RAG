"""Pruebas del bucle de terminal sin cargar recursos ni modelos reales."""

from pathlib import Path
import sys

import pytest


MITECO_RAG_PATH = Path(__file__).resolve().parents[1] / "src" / "miteco_rag"
if str(MITECO_RAG_PATH) not in sys.path:
    sys.path.insert(0, str(MITECO_RAG_PATH))

import main_langgraph  # noqa: E402


class FakeClosable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeSaverContext:
    def __init__(self, checkpointer: object) -> None:
        self.checkpointer = checkpointer

    def __enter__(self) -> object:
        return self.checkpointer

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None


def test_main_reuses_resources_and_thread_for_multiple_questions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """El main carga una vez, conversa en bucle y cierra sus recursos."""

    chroma_client = FakeClosable()
    metadata_connection = FakeClosable()
    checkpointer = object()
    graph_calls: list[tuple[dict, dict]] = []
    create_arguments: dict[str, object] = {}

    class FakeGraph:
        def invoke(self, state: dict, config: dict) -> dict[str, str]:
            graph_calls.append((state, config))
            content = state["messages"][0]["content"]
            return {"answer": f"Respuesta a: {content}"}

    def fake_loader():
        return (
            "embedding-model",
            chroma_client,
            "collection",
            "catalog",
        )

    def fake_create_graph(**arguments):
        create_arguments.update(arguments)
        return FakeGraph()

    class FakeSqliteSaver:
        @classmethod
        def from_conn_string(cls, path: str) -> FakeSaverContext:
            assert path == str(tmp_path / "langgraph.sqlite")
            return FakeSaverContext(checkpointer)

    user_inputs = iter(
        [
            "Incendios activos en León",
            "   ",
            "¿Y en Palencia?",
            "salir",
        ]
    )

    monkeypatch.setattr(
        main_langgraph,
        "CHECKPOINT_PATH",
        tmp_path / "langgraph.sqlite",
    )
    monkeypatch.setattr(main_langgraph, "loader", fake_loader)
    monkeypatch.setattr(
        main_langgraph,
        "load_metadata_connection",
        lambda: metadata_connection,
    )
    monkeypatch.setattr(
        main_langgraph,
        "create_graph",
        fake_create_graph,
    )
    monkeypatch.setattr(main_langgraph, "SqliteSaver", FakeSqliteSaver)
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: next(user_inputs),
    )

    main_langgraph.main()

    assert len(graph_calls) == 2
    assert graph_calls[0][0] == {
        "messages": [
            {
                "role": "user",
                "content": "Incendios activos en León",
            }
        ]
    }
    assert graph_calls[1][0] == {
        "messages": [
            {
                "role": "user",
                "content": "¿Y en Palencia?",
            }
        ]
    }
    assert graph_calls[0][1] == graph_calls[1][1]
    assert create_arguments["checkpointer"] is checkpointer
    assert create_arguments["emb_model"] == "embedding-model"
    assert create_arguments["collection"] == "collection"
    assert create_arguments["catalog"] == "catalog"
    assert create_arguments["metadata_connection"] is metadata_connection
    assert chroma_client.closed is True
    assert metadata_connection.closed is True

    output = capsys.readouterr().out
    assert "ID de conversación:" in output
    assert "La pregunta no puede estar vacía" in output
    assert "Respuesta a: Incendios activos en León" in output
    assert "Respuesta a: ¿Y en Palencia?" in output
