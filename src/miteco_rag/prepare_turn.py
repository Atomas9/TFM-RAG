from typing import Literal, TypedDict


class ChatMessage(TypedDict):
    """Mensaje conversacional compatible con ollama.chat()."""

    role: Literal["user", "assistant"]
    content: str


def prepare_turn(messages: list[ChatMessage]) -> dict[str, object]:
    """
    Obtiene la última pregunta del usuario y limpia los resultados técnicos
    pertenecientes al turno anterior.

    El historial de mensajes no se devuelve porque LangGraph ya lo conserva
    mediante el reducer definido en GraphState.
    """

    if not messages:
        raise ValueError(
            "No hay mensajes en la conversación."
        )

    # Recorremos desde el final porque normalmente el último mensaje
    # será precisamente el que acaba de escribir el usuario.
    for message in reversed(messages):
        if message["role"] != "user":
            continue

        user_query = message["content"].strip()

        if not user_query:
            raise ValueError(
                "La pregunta del usuario no puede estar vacía."
            )

        return {
            # Pregunta original del turno.
            "user_query": user_query,

            # Al principio coincide con la pregunta original.
            # RewriteQuery podrá sustituirla posteriormente.
            "query": user_query,

            # Resultados técnicos que no deben heredarse del turno anterior.
            "decision": None,
            "analysis": None,
            "review": None,
            "proposal": None,
            "deterministic_where": None,
            "final_where": None,
            "retrieval_mode": None,
            "raw_context": None,
            "context": "",
            "answer": "",
        }

    raise ValueError(
        "No se ha encontrado ningún mensaje del usuario."
    )


