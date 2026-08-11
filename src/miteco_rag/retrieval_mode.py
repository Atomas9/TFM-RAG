"""Eleccion determinista del tipo de recuperacion que necesita la consulta."""

import re
from typing import Literal

from pydantic import BaseModel


MIN_PATTERNS = (
    r"\b(?:primera|menor)\s+fecha\b",
    r"\bfecha\s+mas\s+antigua\b",
    r"\bdesde\s+que\s+fecha\b",
    r"\b(?:primer|primero)\s+(?:parte|informe|registro|incendio|fuego)\b",
    r"\b(?:parte|informe|registro|incendio|fuego)\s+mas\s+antiguo\b",
)

MAX_PATTERNS = (
    r"\b(?:ultima|mayor)\s+fecha\b",
    r"\bfecha\s+mas\s+reciente\b",
    r"\bhasta\s+que\s+fecha\b",
    r"\bultimo\s+(?:parte|informe|registro|incendio|fuego)\b",
    r"\b(?:parte|informe|registro|incendio|fuego)\s+mas\s+reciente\b",
)

COUNT_PATTERN = re.compile(
    r"\b(?:"
    r"cuantos?"
    r"|numero\s+(?:total\s+)?de"
    r"|(?:total|cantidad)\s+de"
    r")\s+"
    r"(?P<target>"
    r"incendios?|fuegos?"
    r"|registros?|snapshots?"
    r"|partes?|informes?"
    r")\b"
)

TIMELINE_PATTERNS = (
    r"\b(?:evolucion|cronologia|historial|seguimiento)\b",
    r"\bcomo\s+(?:ha\s+)?evolucionado\b",
    r"\bcomo\s+(?:ha\s+)?cambiado\b",
    r"\ba\s+lo\s+largo\s+del\s+tiempo\b",
)


CountTarget = Literal["incidents", "snapshots", "reports"]

COUNT_TARGETS: dict[str, CountTarget] = {
    "incendio": "incidents",
    "incendios": "incidents",
    "fuego": "incidents",
    "fuegos": "incidents",
    "registro": "snapshots",
    "registros": "snapshots",
    "snapshot": "snapshots",
    "snapshots": "snapshots",
    "parte": "reports",
    "partes": "reports",
    "informe": "reports",
    "informes": "reports",
}


class RetrievalMode(BaseModel):
    """Modo de recuperacion y, si procede, extremo solicitado."""

    mode: Literal[
        "hybrid",
        "min_max",
        "count",
        "timeline",
    ]
    operation: Literal["min", "max"] | None = None
    count_target: CountTarget | None = None


def _matches(query: str, patterns: tuple[str, ...]) -> bool:
    """Indica si la consulta normalizada coincide con algun patron."""

    normalized_query = _normalize_query(query)
    return any(re.search(pattern, normalized_query) for pattern in patterns)


def _normalize_query(query: str) -> str:
    """Normaliza las variantes con tilde necesarias para estos patrones."""

    return query.casefold().translate(
        str.maketrans("áéíóúüñ", "aeiouun")
    )


def is_min_query(query: str) -> bool:
    """Detecta consultas que requieren la fecha o registro minimo."""

    return _matches(query, MIN_PATTERNS)


def is_max_query(query: str) -> bool:
    """Detecta consultas que requieren la fecha o registro maximo."""

    return _matches(query, MAX_PATTERNS)


def is_min_max_query(query: str) -> bool:
    """Detecta cualquier consulta de minimo o maximo."""

    return is_min_query(query) or is_max_query(query)


def is_count_query(query: str) -> bool:
    """Detecta consultas que solicitan un recuento."""

    return get_count_target(query) is not None


def get_count_target(query: str) -> CountTarget | None:
    """Indica si deben contarse incendios, snapshots o informes."""

    normalized_query = _normalize_query(query)
    match = COUNT_PATTERN.search(normalized_query)

    if match is None:
        return None

    return COUNT_TARGETS[match.group("target")]


def is_timeline_query(query: str) -> bool:
    """Detecta consultas sobre la evolucion temporal de un incendio."""

    return _matches(query, TIMELINE_PATTERNS)


def choose_retrieval_mode(query: str) -> RetrievalMode:
    """Elige el modo de recuperacion adecuado para la pregunta."""

    if not query.strip():
        raise ValueError("La consulta no puede estar vacia.")

    if is_min_query(query):
        return RetrievalMode(mode="min_max", operation="min")

    if is_max_query(query):
        return RetrievalMode(mode="min_max", operation="max")

    count_target = get_count_target(query)
    if count_target is not None:
        return RetrievalMode(
            mode="count",
            count_target=count_target,
        )

    if is_timeline_query(query):
        return RetrievalMode(mode="timeline")

    return RetrievalMode(mode="hybrid")
