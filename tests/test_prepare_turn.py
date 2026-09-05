"""Pruebas de la preparación de cada turno conversacional."""

import pytest

from miteco_rag.prepare_turn import prepare_turn


def test_prepare_turn_uses_latest_user_message_and_clears_state() -> None:
    messages = [
        {"role": "user", "content": "Incendios activos en León"},
        {"role": "assistant", "content": "Respuesta anterior"},
        {"role": "user", "content": "  ¿Y en Palencia?  "},
    ]

    result = prepare_turn(messages)

    assert result["user_query"] == "¿Y en Palencia?"
    assert result["query"] == "¿Y en Palencia?"
    assert result["decision"] is None
    assert result["analysis"] is None
    assert result["proposal"] is None
    assert result["final_where"] is None
    assert result["raw_context"] is None
    assert result["context"] == ""
    assert result["answer"] == ""
    assert "messages" not in result


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "assistant", "content": "Sin pregunta"}],
    ],
)
def test_prepare_turn_rejects_history_without_user(messages) -> None:
    with pytest.raises(ValueError):
        prepare_turn(messages)


def test_prepare_turn_rejects_empty_latest_user_message() -> None:
    with pytest.raises(ValueError, match="vacía"):
        prepare_turn(
            [{"role": "user", "content": "   "}]
        )
