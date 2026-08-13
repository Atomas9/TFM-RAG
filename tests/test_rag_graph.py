"""Pruebas del routing de LangGraph sin servicios ni bases de datos reales."""

from pathlib import Path
import sys

import pytest


# ``rag_graph.py`` se ejecuta actualmente como script y utiliza imports locales
# como ``from bouncer import bouncer``. Añadimos su directorio para probar el
# mismo modo de importación que usa ``main_langgraph.py`` sin cargar recursos.
MITECO_RAG_PATH = Path(__file__).resolve().parents[1] / "src" / "miteco_rag"
if str(MITECO_RAG_PATH) not in sys.path:
    sys.path.insert(0, str(MITECO_RAG_PATH))

import rag_graph  # noqa: E402


EMPTY_RESULT: rag_graph.RetrievalResult = {
    "mode": "hybrid",
    "ids": [],
    "documents": [],
    "metadatas": [],
    "distances": [],
    "aggregate": None,
}


@pytest.mark.parametrize(
    ("query", "expected_mode", "expected_retrieval"),
    [
        (
            "¿Qué incendios activos hay en León?",
            "hybrid",
            "hybrid",
        ),
        (
            "¿Cuál es la última fecha registrada en León?",
            "min_max",
            "min_max",
        ),
        (
            "¿Cuántos incendios hubo en León?",
            "count",
            "count",
        ),
    ],
)
def test_keep_routes_to_expected_retrieval_and_converges(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    expected_mode: str,
    expected_retrieval: str,
) -> None:
    """Las tres ramas llegan al retrieval correcto y a la generación común."""

    calls: list[str] = []
    expected_where = {"province_normalized": "leon"}

    def fake_bouncer_node(state):
        calls.append("bouncer")
        return {"decision": "GO"}

    def fake_analysis_node(state, catalog):
        calls.append("analysis")
        return {
            "analysis": {},
            "deterministic_where": expected_where,
        }

    def fake_reviewer_node(state):
        calls.append("reviewer")
        return {
            "review": {"action": "keep"},
            "final_where": state["deterministic_where"],
        }

    def make_retrieval_node(name: str):
        def retrieval_node(state, **dependencies):
            calls.append(name)
            assert state["final_where"] == expected_where
            return {
                "raw_context": {
                    **EMPTY_RESULT,
                    "mode": name,
                }
            }

        return retrieval_node

    def fake_context_node(state):
        calls.append("context")
        assert state["raw_context"]["mode"] == expected_retrieval
        return {"context": f"Contexto {expected_retrieval}"}

    def fake_answer_node(state):
        calls.append("answer")
        return {"answer": f"Respuesta {state['context']}"}

    monkeypatch.setattr(rag_graph, "bouncer_node", fake_bouncer_node)
    monkeypatch.setattr(
        rag_graph,
        "deterministic_analysis_node",
        fake_analysis_node,
    )
    monkeypatch.setattr(rag_graph, "reviewer_node", fake_reviewer_node)
    monkeypatch.setattr(
        rag_graph,
        "retrieve_node",
        make_retrieval_node("hybrid"),
    )
    monkeypatch.setattr(
        rag_graph,
        "min_max_retrieve_node",
        make_retrieval_node("min_max"),
    )
    monkeypatch.setattr(
        rag_graph,
        "count_retrieve_node",
        make_retrieval_node("count"),
    )
    monkeypatch.setattr(rag_graph, "context_node", fake_context_node)
    monkeypatch.setattr(rag_graph, "generate_answer_node", fake_answer_node)

    graph = rag_graph.create_graph(
        checkpointer=None,
        emb_model=object(),
        collection=object(),
        catalog=object(),
        metadata_connection=object(),
    )

    result = graph.invoke({"query": query})

    assert result["retrieval_mode"]["mode"] == expected_mode
    assert result["final_where"] == expected_where
    assert result["answer"] == f"Respuesta Contexto {expected_retrieval}"
    assert calls == [
        "bouncer",
        "analysis",
        "reviewer",
        expected_retrieval,
        "context",
        "answer",
    ]


def test_no_go_stops_before_analysis_and_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una consulta rechazada termina sin analizar ni recuperar documentos."""

    def fake_bouncer_node(state):
        return {
            "decision": "NO GO",
            "answer": "Pregunta no relacionada con incendios",
        }

    def forbidden_node(*args, **kwargs):
        pytest.fail("No debía ejecutarse ningún nodo posterior al bouncer")

    monkeypatch.setattr(rag_graph, "bouncer_node", fake_bouncer_node)
    monkeypatch.setattr(
        rag_graph,
        "deterministic_analysis_node",
        forbidden_node,
    )
    monkeypatch.setattr(rag_graph, "retrieve_node", forbidden_node)
    monkeypatch.setattr(rag_graph, "min_max_retrieve_node", forbidden_node)
    monkeypatch.setattr(rag_graph, "count_retrieve_node", forbidden_node)

    graph = rag_graph.create_graph(
        checkpointer=None,
        emb_model=object(),
        collection=object(),
        catalog=object(),
        metadata_connection=object(),
    )

    result = graph.invoke({"query": "¿Qué hora es?"})

    assert result["decision"] == "NO GO"
    assert result["answer"] == "Pregunta no relacionada con incendios"
    assert "retrieval_mode" not in result
    assert "raw_context" not in result


def test_clarify_stops_before_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La acción clarify termina después del revisor y conserva su respuesta."""

    calls: list[str] = []

    def fake_bouncer_node(state):
        calls.append("bouncer")
        return {"decision": "GO"}

    def fake_analysis_node(state, catalog):
        calls.append("analysis")
        return {
            "analysis": {},
            "deterministic_where": None,
        }

    def fake_reviewer_node(state):
        calls.append("reviewer")
        return {
            "review": {"action": "clarify"},
            "answer": "La consulta necesita una aclaración",
        }

    def forbidden_node(*args, **kwargs):
        pytest.fail("No debía ejecutarse un retrieval después de clarify")

    monkeypatch.setattr(rag_graph, "bouncer_node", fake_bouncer_node)
    monkeypatch.setattr(
        rag_graph,
        "deterministic_analysis_node",
        fake_analysis_node,
    )
    monkeypatch.setattr(rag_graph, "reviewer_node", fake_reviewer_node)
    monkeypatch.setattr(rag_graph, "retrieve_node", forbidden_node)
    monkeypatch.setattr(rag_graph, "min_max_retrieve_node", forbidden_node)
    monkeypatch.setattr(rag_graph, "count_retrieve_node", forbidden_node)

    graph = rag_graph.create_graph(
        checkpointer=None,
        emb_model=object(),
        collection=object(),
        catalog=object(),
        metadata_connection=object(),
    )

    result = graph.invoke({"query": "¿Te refieres a León o a Palencia?"})

    assert calls == ["bouncer", "analysis", "reviewer"]
    assert result["review"]["action"] == "clarify"
    assert result["answer"] == "La consulta necesita una aclaración"
    assert "retrieval_mode" not in result


def test_replace_resolves_where_before_selecting_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replace genera el filtro nuevo y el retrieval recibe ese filtro final."""

    calls: list[str] = []
    deterministic_where = {
        "$and": [
            {"province_normalized": "leon"},
            {"autonomous_community_normalized": "andalucia"},
        ]
    }
    resolved_where = {
        "$or": [
            {"province_normalized": "leon"},
            {"autonomous_community_normalized": "andalucia"},
        ]
    }

    def fake_bouncer_node(state):
        return {"decision": "GO"}

    def fake_analysis_node(state, catalog):
        return {
            "analysis": {},
            "deterministic_where": deterministic_where,
        }

    def fake_reviewer_node(state):
        return {"review": {"action": "replace"}}

    def fake_generate_filter_node(state, catalog):
        calls.append("generate_filter")
        return {"proposal": {"groups": []}}

    def fake_resolve_where_node(state):
        calls.append("resolve_where")
        assert state["deterministic_where"] == deterministic_where
        return {"final_where": resolved_where}

    def fake_count_node(state, **dependencies):
        calls.append("count")
        assert state["final_where"] == resolved_where
        return {
            "raw_context": {
                **EMPTY_RESULT,
                "mode": "count",
                "distances": None,
                "aggregate": {
                    "count_target": "incidents",
                    "value": 4,
                },
            }
        }

    def fake_context_node(state):
        return {"context": "Recuento: 4"}

    def fake_answer_node(state):
        return {"answer": "Hay 4 incendios."}

    monkeypatch.setattr(rag_graph, "bouncer_node", fake_bouncer_node)
    monkeypatch.setattr(
        rag_graph,
        "deterministic_analysis_node",
        fake_analysis_node,
    )
    monkeypatch.setattr(rag_graph, "reviewer_node", fake_reviewer_node)
    monkeypatch.setattr(
        rag_graph,
        "generate_filter_node",
        fake_generate_filter_node,
    )
    monkeypatch.setattr(
        rag_graph,
        "resolve_where_node",
        fake_resolve_where_node,
    )
    monkeypatch.setattr(rag_graph, "count_retrieve_node", fake_count_node)
    monkeypatch.setattr(rag_graph, "context_node", fake_context_node)
    monkeypatch.setattr(rag_graph, "generate_answer_node", fake_answer_node)

    graph = rag_graph.create_graph(
        checkpointer=None,
        emb_model=object(),
        collection=object(),
        catalog=object(),
        metadata_connection=object(),
    )

    result = graph.invoke(
        {"query": "¿Cuántos incendios hubo en León y Andalucía?"}
    )

    assert calls == ["generate_filter", "resolve_where", "count"]
    assert result["deterministic_where"] == deterministic_where
    assert result["final_where"] == resolved_where
    assert result["retrieval_mode"]["mode"] == "count"
    assert result["answer"] == "Hay 4 incendios."


@pytest.mark.parametrize(
    ("mode", "expected_route"),
    [
        ("hybrid", "hybrid"),
        ("min_max", "min_max"),
        ("count", "count"),
    ],
)
def test_route_after_retrieval_mode(
    mode: str,
    expected_route: str,
) -> None:
    """La función condicional expone una salida por cada modo implementado."""

    state = {"retrieval_mode": {"mode": mode}}

    assert rag_graph.route_after_retrieval_mode(state) == expected_route


def test_min_max_node_passes_operation_and_final_where(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El nodo reconstruye el plan y pasa su operación al retrieval exacto."""

    collection = object()
    connection = object()
    where = {"province_normalized": "leon"}
    expected_result: rag_graph.RetrievalResult = {
        **EMPTY_RESULT,
        "mode": "min_max",
        "distances": None,
        "aggregate": {
            "operation": "max",
            "report_date_number": 20260713,
        },
    }

    def fake_retrieve_min_max(
        received_collection,
        received_connection,
        received_where,
        received_operation,
    ):
        assert received_collection is collection
        assert received_connection is connection
        assert received_where == where
        assert received_operation == "max"
        return expected_result

    monkeypatch.setattr(
        rag_graph,
        "retrieve_min_max",
        fake_retrieve_min_max,
    )

    result = rag_graph.min_max_retrieve_node(
        {
            "final_where": where,
            "retrieval_mode": {
                "mode": "min_max",
                "operation": "max",
                "count_target": None,
            },
        },
        collection=collection,
        metadata_connection=connection,
    )

    assert result == {"raw_context": expected_result}


def test_count_node_passes_target_and_final_where(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El nodo reconstruye el objetivo y lo entrega al recuento SQLite."""

    connection = object()
    where = {"status": "ACTIVO"}
    expected_result: rag_graph.RetrievalResult = {
        **EMPTY_RESULT,
        "mode": "count",
        "distances": None,
        "aggregate": {
            "count_target": "incidents",
            "value": 3,
        },
    }

    def fake_retrieve_count(
        received_connection,
        received_where,
        received_target,
    ):
        assert received_connection is connection
        assert received_where == where
        assert received_target == "incidents"
        return expected_result

    monkeypatch.setattr(rag_graph, "retrieve_count", fake_retrieve_count)

    result = rag_graph.count_retrieve_node(
        {
            "final_where": where,
            "retrieval_mode": {
                "mode": "count",
                "operation": None,
                "count_target": "incidents",
            },
        },
        metadata_connection=connection,
    )

    assert result == {"raw_context": expected_result}
