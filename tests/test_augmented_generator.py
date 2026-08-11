"""Pruebas del formateo de contexto y del generador aumentado."""

from types import SimpleNamespace

from miteco_rag import augmented_generator


def test_generate_context_joins_numbered_chunks() -> None:
    raw_context = {
        "mode": "hybrid",
        "ids": ["snapshot-1", "snapshot-2"],
        "documents": ["Contenido uno", "Contenido dos"],
        "metadatas": [{}, {}],
        "distances": [0.1, 0.2],
        "aggregate": None,
    }

    context = augmented_generator.generate_context(raw_context)

    assert context == (
        "[CHUNK 1]\nContenido uno"
        "\n\n---\n\n"
        "[CHUNK 2]\nContenido dos"
    )


def test_generate_context_returns_empty_string_without_documents() -> None:
    raw_context = {
        "mode": "hybrid",
        "ids": [],
        "documents": [],
        "metadatas": [],
        "distances": [],
        "aggregate": None,
    }

    assert augmented_generator.generate_context(raw_context) == ""


def test_generate_context_includes_aggregate_and_documents() -> None:
    raw_context = {
        "mode": "min_max",
        "ids": ["snapshot-1"],
        "documents": ["Contenido del último parte"],
        "metadatas": [{}],
        "distances": None,
        "aggregate": {
            "operation": "max",
            "report_date_number": 20260801,
        },
    }

    context = augmented_generator.generate_context(raw_context)

    assert "[RESULTADO ESTRUCTURADO]" in context
    assert '"operation": "max"' in context
    assert '"report_date_number": 20260801' in context
    assert "[CHUNK 1]\nContenido del último parte" in context


def test_zero_count_is_preserved_as_retrieved_data(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_chat(*, model, messages):
        captured["messages"] = messages
        return SimpleNamespace(
            message=SimpleNamespace(content="No constan incendios.")
        )

    monkeypatch.setattr(augmented_generator.ollama, "chat", fake_chat)

    raw_context = {
        "mode": "count",
        "ids": [],
        "documents": [],
        "metadatas": [],
        "distances": None,
        "aggregate": {
            "count_target": "incidents",
            "value": 0,
        },
    }
    context = augmented_generator.generate_context(raw_context)

    augmented_generator.generate_answer(
        query="¿Cuántos incendios hay en Oviedo?",
        context=context,
        where={"location_normalized": "oviedo"},
    )

    messages = captured["messages"]
    assert "WITH_DATA" in messages[1]["content"]
    assert '"value": 0' in messages[1]["content"]


def test_empty_context_sends_filter_and_no_records_to_ollama(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_chat(*, model, messages):
        captured["messages"] = messages
        return SimpleNamespace(
            message=SimpleNamespace(
                content="No constan registros en Oviedo."
            )
        )

    monkeypatch.setattr(augmented_generator.ollama, "chat", fake_chat)

    answer = augmented_generator.generate_answer(
        query="¿Hay incendios en Oviedo ahora?",
        context="",
        where={
            "$and": [
                {"location_normalized": "oviedo"},
                {"report_date_number": 20260719},
            ]
        },
    )

    assert answer == "No constan registros en Oviedo."

    messages = captured["messages"]
    assert "NO_DATA" in messages[1]["content"]
    assert '"location_normalized": "oviedo"' in messages[1]["content"]
    assert '"report_date_number": 20260719' in messages[1]["content"]
    assert "[No se recuperaron datos.]" in messages[1]["content"]


def test_generate_answer_sends_question_and_context_to_ollama(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_chat(*, model, messages):
        captured["model"] = model
        captured["messages"] = messages
        return SimpleNamespace(
            message=SimpleNamespace(content="Respuesta fundamentada")
        )

    monkeypatch.setattr(augmented_generator.ollama, "chat", fake_chat)

    answer = augmented_generator.generate_answer(
        query="¿Qué ocurrió en Villablino?",
        context="[CHUNK 1]\nDatos del incendio",
        where={"location_normalized": "villablino"},
        model_name="modelo-prueba",
    )

    assert answer == "Respuesta fundamentada"
    assert captured["model"] == "modelo-prueba"

    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "WITH_DATA" in messages[1]["content"]
    assert "¿Qué ocurrió en Villablino?" in messages[1]["content"]
    assert '"location_normalized": "villablino"' in messages[1]["content"]
    assert "[CHUNK 1]\nDatos del incendio" in messages[1]["content"]
