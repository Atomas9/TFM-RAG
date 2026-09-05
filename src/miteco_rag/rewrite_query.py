import ollama

if __package__:
    from .prepare_turn import ChatMessage
else:
    from prepare_turn import ChatMessage

OLLAMA_MODEL = 'gemma4:31b-cloud'
MAX_HISTORY_MESSAGES = 8

SYSTEM_PROMPT = """
Eres el componente encargado de reescribir preguntas dentro de un sistema RAG
sobre los partes de incendios forestales publicados por MITECO.

Tu tarea consiste en convertir la última pregunta del usuario en una consulta
independiente que pueda entenderse sin leer la conversación anterior.

Utiliza los mensajes anteriores únicamente para resolver referencias como:

- "¿Y en Palencia?"
- "¿Y los controlados?"
- "¿Cuántos hubo allí?"
- "¿Cuál fue el último?"
- "¿Y durante agosto?"

REGLAS

- Conserva el idioma de la última pregunta.
- Conserva exactamente su intención.
- Utiliza solo el contexto necesario de la conversación anterior.
- Mantén las ubicaciones, fechas, estados y situaciones operativas mencionadas.
- Mantén correctamente inclusiones y exclusiones.
- No elimines ni cambies negaciones.
- No inventes provincias, localidades, fechas, estados ni condiciones.
- No añadas información que no aparezca en la conversación.
- No respondas la pregunta.
- No expliques la reescritura.
- No devuelvas Markdown, comillas, prefijos ni JSON.
- Devuelve exclusivamente la consulta reescrita como texto.
- Si la última pregunta ya es independiente, devuélvela sin cambios.

EJEMPLO

Conversación:

Usuario:
¿Qué incendios activos hay en León?

Asistente:
En los partes indexados constan varios incendios activos en León.

Usuario:
¿Y en Palencia?

Consulta reescrita:

¿Qué incendios activos hay en Palencia?
""".strip()

def rewrite_query(
    messages: list[ChatMessage],
    model_name: str = OLLAMA_MODEL,
    max_history_messages: int = MAX_HISTORY_MESSAGES,
) -> str:
    """
    Convierte la última pregunta en una consulta independiente.

    En el primer turno devuelve directamente la pregunta original para evitar
    una llamada innecesaria al LLM.
    """

    if not messages:
        raise ValueError(
            "No hay mensajes para reescribir la consulta."
        )

    user_messages = [
        message
        for message in messages
        if message["role"] == "user"
    ]

    if not user_messages:
        raise ValueError(
            "No se ha encontrado ningún mensaje del usuario."
        )

    latest_query = user_messages[-1]["content"].strip()

    if not latest_query:
        raise ValueError(
            "La pregunta del usuario no puede estar vacía."
        )

    # En el primer turno no existe contexto anterior que resolver.
    if len(user_messages) == 1:
        return latest_query

    # Conservamos todo el historial en GraphState, pero solo enviamos
    # los mensajes más recientes al modelo.
    conversation_messages = messages[-max_history_messages:]

    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        *conversation_messages,
    ]

    response = ollama.chat(
        model=model_name,
        messages=messages,
        options={
            "temperature": 0,
        },
    )

    rewritten_query = response.message.content.strip()

    if not rewritten_query:
        raise ValueError(
            "El modelo no ha generado una consulta reescrita."
        )

    return rewritten_query
