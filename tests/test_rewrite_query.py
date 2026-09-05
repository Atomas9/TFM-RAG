"""Pruebas de reescritura conversacional con Ollama simulado."""

from types import SimpleNamespace

import pytest

from miteco_rag import rewrite_query as rewrite_query_module


def test_first_user_turn_does_not_call_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_chat(**kwargs):
        pytest.fail("El primer turno no debe llamar a Ollama")

    monkeypatch.setattr(
        rewrite_query_module.ollama,
        "chat",
        forbidden_chat,
    )

    result = rewrite_query_module.rewrite_query(
        [{"role": "user", "content": "  Incendios en León  "}]
    )

    assert result == "Incendios en León"


def test_follow_up_sends_recent_history_to_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = [
        {"role": "user", "content": "Incendios activos en León"},
        {"role": "assistant", "content": "Constan varios registros."},
        {"role": "user", "content": "¿Y en Palencia?"},
    ]
    received: dict[str, object] = {}

    def fake_chat(**kwargs):
        received.update(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(
                content="  ¿Qué incendios activos hay en Palencia?  "
            )
        )

    monkeypatch.setattr(
        rewrite_query_module.ollama,
        "chat",
        fake_chat,
    )

    result = rewrite_query_module.rewrite_query(
        history,
        model_name="modelo-prueba",
        max_history_messages=2,
    )

    assert result == "¿Qué incendios activos hay en Palencia?"
    assert received["model"] == "modelo-prueba"
    assert received["options"] == {"temperature": 0}
    assert received["messages"][0]["role"] == "system"
    assert received["messages"][1:] == history[-2:]


def test_rewrite_query_rejects_history_without_user() -> None:
    with pytest.raises(ValueError):
        rewrite_query_module.rewrite_query(
            [{"role": "assistant", "content": "Respuesta"}]
        )


def test_rewrite_query_rejects_empty_model_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rewrite_query_module.ollama,
        "chat",
        lambda **kwargs: SimpleNamespace(
            message=SimpleNamespace(content="   ")
        ),
    )

    history = [
        {"role": "user", "content": "Incendios en León"},
        {"role": "assistant", "content": "Respuesta"},
        {"role": "user", "content": "¿Y en Palencia?"},
    ]

    with pytest.raises(ValueError, match="no ha generado"):
        rewrite_query_module.rewrite_query(history)
