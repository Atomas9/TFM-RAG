"""Versión didáctica del flujo principal utilizando LangGraph.

Este archivo no sustituye a ``main.py``. Su objetivo es mostrar cómo las
funciones que ya existen en el proyecto pueden conectarse mediante un grafo.

La idea fundamental de LangGraph es:

1. El estado guarda la información compartida por el flujo.
2. Cada nodo lee el estado y devuelve únicamente los datos que añade.
3. Las rutas condicionales deciden cuál será el siguiente nodo.
"""

from typing import Literal, TypedDict

from chromadb.api.types import QueryResult
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from augmented_generator import generate_answer, generate_context
from bouncer import BouncerDecision, bouncer
from core import loader
from generate_filter_LLM import (
    FilterProposal,
    generate_filter_llm,
    resolve_final_where,
)
from query_filters import DeterministicAnalysis
from query_filters import build_deterministic_analysis
from retrieval_chroma import retrieve
from revisor_query_filters import FilterReview, revisor


class RAGState(TypedDict, total=False):
    """Información que los nodos comparten durante una ejecución."""

    query: str
    decision: BouncerDecision
    analysis: DeterministicAnalysis
    review: FilterReview
    proposal: FilterProposal
    where: dict[str, object] | None
    raw_context: QueryResult
    context: str
    answer: str


def create_graph():
    """Carga los recursos una vez, define los nodos y construye el grafo."""

    # Estos tres objetos se reutilizan durante todo el flujo. No se guardan en
    # RAGState porque son recursos, no resultados producidos por los nodos.
    embedding_model, collection, catalog = loader()

    # ------------------------------------------------------------------
    # NODOS
    # ------------------------------------------------------------------
    # Un nodo recibe el estado y devuelve solo los campos que ha calculado.

    def bouncer_node(state: RAGState) -> dict:
        decision = bouncer(state["query"])

        result = {"decision": decision}
        if decision.decision == "NO GO":
            result["answer"] = "Pregunta no relacionada con incendios"

        return result

    def deterministic_analysis_node(state: RAGState) -> dict:
        analysis = build_deterministic_analysis(
            state["query"],
            catalog,
        )
        return {
            "analysis": analysis,
            "where": analysis.deterministic_where,
        }

    def reviewer_node(state: RAGState) -> dict:
        review = revisor(
            state["query"],
            state["analysis"],
        )

        result = {"review": review}
        if review.action == "clarify":
            issues = "\n".join(f"- {issue}" for issue in review.issues)
            result["answer"] = (
                "La consulta necesita una aclaración:\n"
                f"{issues}"
            )

        return result

    def generate_filter_node(state: RAGState) -> dict:
        proposal = generate_filter_llm(
            state["query"],
            state["analysis"],
            state["review"],
            catalog,
        )
        return {"proposal": proposal}

    def resolve_where_node(state: RAGState) -> dict:
        where = resolve_final_where(
            state["analysis"],
            state["review"],
            state.get("proposal"),
        )
        return {"where": where}

    def retrieve_node(state: RAGState) -> dict:
        raw_context = retrieve(
            state["query"],
            embedding_model,
            collection,
            state.get("where"),
            top_k=10,
        )
        return {"raw_context": raw_context}

    def generate_context_node(state: RAGState) -> dict:
        context = generate_context(state["raw_context"])
        return {"context": context}

    def generate_answer_node(state: RAGState) -> dict:
        answer = generate_answer(
            state["query"],
            state["context"],
            state.get("where"),
        )
        return {"answer": answer}

    # ------------------------------------------------------------------
    # RUTAS CONDICIONALES
    # ------------------------------------------------------------------
    # Estas funciones no modifican el estado. Solo indican qué camino seguir.

    def route_after_bouncer(state: RAGState) -> Literal["continue", "end"]:
        if state["decision"].decision == "GO":
            return "continue"
        return "end"

    def route_after_review(
        state: RAGState,
    ) -> Literal["generate", "keep", "end"]:
        action = state["review"].action

        if action in {"extend", "replace"}:
            return "generate"
        if action == "keep":
            return "keep"
        return "end"

    # ------------------------------------------------------------------
    # CONSTRUCCIÓN DEL GRAFO
    # ------------------------------------------------------------------

    graph = StateGraph(RAGState)

    graph.add_node("bouncer", bouncer_node)
    graph.add_node("deterministic_analysis", deterministic_analysis_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("generate_filter", generate_filter_node)
    graph.add_node("resolve_where", resolve_where_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate_context", generate_context_node)
    graph.add_node("generate_answer", generate_answer_node)

    graph.add_edge(START, "bouncer")

    graph.add_conditional_edges(
        "bouncer",
        route_after_bouncer,
        {
            "continue": "deterministic_analysis",
            "end": END,
        },
    )

    graph.add_edge("deterministic_analysis", "reviewer")

    graph.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "generate": "generate_filter",
            "keep": "resolve_where",
            "end": END,
        },
    )

    graph.add_edge("generate_filter", "resolve_where")
    graph.add_edge("resolve_where", "retrieve")
    graph.add_edge("retrieve", "generate_context")
    graph.add_edge("generate_context", "generate_answer")
    graph.add_edge("generate_answer", END)

    # MemorySaver conserva los estados mientras este proceso de Python siga
    # abierto. Más adelante se puede sustituir por SQLite para persistirlos.
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


def main() -> None:
    graph = create_graph()
    query = input("Escribe tu pregunta: ")

    # El thread_id identifica la conversación asociada a los checkpoints.
    config = {"configurable": {"thread_id": "terminal-session"}}

    final_state = graph.invoke(
        {"query": query},
        config=config,
    )

    print("\nRespuesta:\n")
    print(final_state["answer"])


if __name__ == "__main__":
    main()
