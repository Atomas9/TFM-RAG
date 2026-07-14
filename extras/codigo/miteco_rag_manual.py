"""RAG manual para partes diarios de incendios de MITECO.

El flujo implementado es:

1. Parsear los PDF y crear un chunk por incendio/localización.
2. Guardar metadatos estructurados (fecha, ubicación, provincia, etc.).
3. Crear embeddings locales con Sentence Transformers.
4. Buscar por filtros de metadatos, similitud coseno o ambas cosas.
5. Construir un contexto y generar la respuesta con un modelo local de Ollama.

Pensado como base educativa y para volúmenes pequeños/medios. La búsqueda
vectorial es exhaustiva con NumPy; si el corpus crece mucho, puede sustituirse
por Qdrant, pgvector, Chroma, etc., manteniendo el resto del flujo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from pypdf import PdfReader


# -----------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# -----------------------------------------------------------------------------

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")
DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

# Líneas en mayúsculas que aparecen en la cabecera pero no representan
# comunidad autónoma o provincia.
NON_GEOGRAPHIC_HEADINGS = {
    "SUBDIRECCIÓN GENERAL DE POLÍTICA FORESTAL Y LUCHA CONTRA LA DESERTIFICACIÓN",
    "SECRETARÍA DE ESTADO DE MEDIO AMBIENTE",
    "ÁREA DE DEFENSA CONTRA INCENDIOS FORESTALES",
    "DIRECCIÓN GENERAL DE BIODIVERSIDAD, BOSQUES Y DESERTIFICACIÓN",
    "INTERVENCIONES DE MEDIOS DEL MINISTERIO PARA LA TRANSICIÓN ECOLÓGICA Y EL RETO DEMOGRÁFICO PARA APOYAR A LAS COMUNIDADES AUTÓNOMAS EN LA EXTINCIÓN DE INCENDIOS FORESTALES",
    "ACTUACIONES DE LOS MEDIOS DEL MINISTERIO",
}


# -----------------------------------------------------------------------------
# MODELO DE DATOS: UN CHUNK REPRESENTA UN INCENDIO
# -----------------------------------------------------------------------------

@dataclass(slots=True)
class FireChunk:
    """Fragmento indexable correspondiente a un incendio/localización."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


# -----------------------------------------------------------------------------
# UTILIDADES DE NORMALIZACIÓN
# -----------------------------------------------------------------------------

def normalize_for_match(value: str | None) -> str:
    """Normaliza texto para comparar filtros ignorando mayúsculas y acentos."""
    if not value:
        return ""

    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def clean_line(line: str) -> str:
    """Limpia espacios de una línea sin destruir su contenido semántico."""
    return re.sub(r"\s+", " ", line).strip()


def parse_iso_date(value: str) -> date:
    """Convierte YYYY-MM-DD en date y lanza un error claro si es inválido."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Fecha inválida '{value}'. Usa el formato YYYY-MM-DD.") from exc


# -----------------------------------------------------------------------------
# FASE 1: EXTRACCIÓN Y PARSEO DE LOS PDF
# -----------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> tuple[list[str], str]:
    """Extrae el texto página a página y devuelve también el texto completo."""
    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return pages, "\n".join(pages)


def extract_document_date(full_text: str) -> str:
    """Extrae la fecha principal del parte y la devuelve como YYYY-MM-DD."""
    # Formato habitual: "domingo, 5 de julio de 2026".
    pattern = re.compile(
        r"(?:lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)?"
        r"\s*,?\s*(\d{1,2})\s+de\s+"
        r"(" + "|".join(SPANISH_MONTHS) + r")\s+de\s+(\d{4})",
        flags=re.IGNORECASE,
    )
    match = pattern.search(full_text)

    if match:
        day = int(match.group(1))
        month = SPANISH_MONTHS[match.group(2).lower()]
        year = int(match.group(3))
        return date(year, month, day).isoformat()

    # Formato alternativo que aparece en algunos documentos/mapas: 05/07/2026.
    match = re.search(r"\bFecha:\s*(\d{2})/(\d{2})/(\d{4})\b", full_text, re.IGNORECASE)
    if match:
        day, month, year = map(int, match.groups())
        return date(year, month, day).isoformat()

    raise ValueError("No se pudo extraer la fecha principal del documento.")


def extract_last_update(full_text: str) -> str | None:
    """Extrae la última actualización del documento en formato ISO si existe."""
    pattern = re.compile(
        r"Última\s+actualización:\s*"
        r"(\d{1,2}:\d{2}(?::\d{2})?)\s*"
        r"(?:del\s+día\s*)?(\d{2})/(\d{2})/(\d{4})",
        flags=re.IGNORECASE,
    )
    match = pattern.search(full_text)
    if not match:
        return None

    time_value, day, month, year = match.groups()
    if len(time_value.split(":")) == 2:
        time_value += ":00"

    return f"{year}-{month}-{day}T{time_value}"


def is_geographic_heading(line: str) -> bool:
    """Detecta líneas en mayúsculas que pueden ser comunidad o provincia."""
    line = clean_line(line)
    if not line or len(line) > 80:
        return False

    # Orígenes de medios como "(ASTURIAS)" pueden quedar en una línea
    # independiente al extraer el PDF, pero no son encabezados geográficos.
    if line.startswith("(") and line.endswith(")"):
        return False

    normalized = normalize_for_match(line)
    excluded = {normalize_for_match(value) for value in NON_GEOGRAPHIC_HEADINGS}
    if normalized in excluded:
        return False

    # Debe contener letras y ser esencialmente una línea en mayúsculas.
    has_letters = any(char.isalpha() for char in line)
    return has_letters and line == line.upper() and ":" not in line


def parse_miteco_pdf(pdf_path: str | Path) -> list[FireChunk]:
    """Convierte un PDF de MITECO en una lista con un chunk por incendio.

    El parser se apoya en la estructura repetida del documento:

    COMUNIDAD
    PROVINCIA
    Localización: ...
    Estado del Incendio: ...
    Medios asignados...
    Nota: ...

    Puede requerir pequeños ajustes si MITECO cambia el formato del PDF.
    """
    pdf_path = Path(pdf_path)
    page_texts, full_text = extract_pdf_text(pdf_path)

    document_date = extract_document_date(full_text)
    last_update = extract_last_update(full_text)

    # Conservamos líneas para identificar los encabezados y los límites de bloque.
    lines: list[str] = []
    for page_text in page_texts:
        lines.extend(clean_line(line) for line in page_text.splitlines() if clean_line(line))

    location_positions = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^Localizaci[oó]n\s*:", line, flags=re.IGNORECASE)
    ]

    if not location_positions:
        raise ValueError(f"No se encontraron bloques 'Localización:' en {pdf_path.name}.")

    chunks: list[FireChunk] = []

    def headings_immediately_before(position: int) -> list[str]:
        """Devuelve hasta dos encabezados consecutivos justo antes del incendio."""
        found: list[str] = []
        cursor = position - 1
        while cursor >= 0 and len(found) < 2 and is_geographic_heading(lines[cursor]):
            found.append(lines[cursor])
            cursor -= 1
        return list(reversed(found))

    headings_by_location = {
        position: headings_immediately_before(position)
        for position in location_positions
    }

    current_community: str | None = None

    for location_number, start in enumerate(location_positions):
        headings = headings_by_location[start]

        # Cuando aparecen dos encabezados, el primero es comunidad/territorio y
        # el segundo provincia. Si solo aparece uno (p. ej. ZAMORA tras LEÓN),
        # mantenemos la comunidad anterior y actualizamos únicamente provincia.
        if len(headings) >= 2:
            current_community = headings[-2]
            province = headings[-1]
        elif len(headings) == 1:
            province = headings[-1]
        else:
            province = None

        autonomous_community = current_community

        if location_number + 1 < len(location_positions):
            next_start = location_positions[location_number + 1]
            # Los encabezados del siguiente incendio no pertenecen al actual.
            end = next_start - len(headings_by_location[next_start])
        else:
            summary_positions = [
                idx
                for idx in range(start + 1, len(lines))
                if lines[idx].startswith("ACTUACIONES DE LOS MEDIOS DEL MINISTERIO")
            ]
            end = summary_positions[0] if summary_positions else len(lines)

        block_lines = lines[start:end]
        block_text = "\n".join(block_lines)

        location_match = re.match(
            r"^Localizaci[oó]n\s*:\s*(.+)$",
            block_lines[0],
            flags=re.IGNORECASE,
        )
        if not location_match:
            continue

        location = clean_line(location_match.group(1))

        state_match = re.search(
            r"Estado\s+del\s+Incendio\s*:\s*([A-ZÁÉÍÓÚÜÑ]+)",
            block_text,
            flags=re.IGNORECASE,
        )
        state = state_match.group(1).upper() if state_match else None

        operational_match = re.search(
            r"S\.O\s*:\s*([A-Z0-9]+)",
            block_text,
            flags=re.IGNORECASE,
        )
        operational_status = operational_match.group(1).upper() if operational_match else None

        note_match = re.search(r"Nota\s*:\s*(.+)$", block_text, flags=re.IGNORECASE | re.DOTALL)
        note = clean_line(note_match.group(1)) if note_match else None

        metadata = {
            "document_date": document_date,
            "last_update": last_update,
            "autonomous_community": autonomous_community,
            "province": province,
            "location": location,
            "state": state,
            "operational_status": operational_status,
            "note": note,
            "source": pdf_path.name,
        }

        # Añadimos los metadatos principales al propio texto. Esto ayuda al modelo
        # de embeddings a recuperar consultas como "incendios en Castellón".
        semantic_text = "\n".join(
            part
            for part in [
                f"Fecha del parte: {document_date}",
                f"Comunidad autónoma: {autonomous_community}" if autonomous_community else None,
                f"Provincia: {province}" if province else None,
                f"Localización: {location}",
                f"Estado: {state}" if state else None,
                f"Situación operativa: {operational_status}" if operational_status else None,
                "Contenido del parte:",
                block_text,
            ]
            if part is not None
        )

        raw_id = f"{pdf_path.name}|{document_date}|{location}|{block_text}"
        chunk_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:20]

        chunks.append(FireChunk(chunk_id=chunk_id, text=semantic_text, metadata=metadata))

    return chunks


def parse_pdf_directory(input_dir: str | Path) -> list[FireChunk]:
    """Parsea todos los PDF de una carpeta y elimina chunks duplicados."""
    input_dir = Path(input_dir)
    pdf_files = sorted(input_dir.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(f"No se encontraron PDF en {input_dir.resolve()}.")

    chunks_by_id: dict[str, FireChunk] = {}
    for pdf_path in pdf_files:
        for chunk in parse_miteco_pdf(pdf_path):
            chunks_by_id[chunk.chunk_id] = chunk

    return list(chunks_by_id.values())


# -----------------------------------------------------------------------------
# FASE 2: EMBEDDINGS E ÍNDICE LOCAL
# -----------------------------------------------------------------------------

def load_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL):
    """Carga el modelo local que convierte textos y consultas en vectores."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def build_and_save_index(
    chunks: list[FireChunk],
    storage_dir: str | Path,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> None:
    """Genera embeddings normalizados y persiste vectores, chunks y configuración."""
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    model = load_embedding_model(embedding_model_name)
    texts = [chunk.text for chunk in chunks]

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype("float32")

    np.save(storage_dir / "embeddings.npy", embeddings)

    with (storage_dir / "chunks.json").open("w", encoding="utf-8") as file:
        json.dump([asdict(chunk) for chunk in chunks], file, ensure_ascii=False, indent=2)

    with (storage_dir / "config.json").open("w", encoding="utf-8") as file:
        json.dump(
            {"embedding_model": embedding_model_name},
            file,
            ensure_ascii=False,
            indent=2,
        )


# -----------------------------------------------------------------------------
# FASE 3: FILTRADO POR METADATOS + SIMILITUD DEL COSENO
# -----------------------------------------------------------------------------

class ManualFireRAG:
    """Carga el índice y ofrece búsqueda híbrida y generación con Ollama."""

    def __init__(self, storage_dir: str | Path):
        self.storage_dir = Path(storage_dir)

        with (self.storage_dir / "chunks.json").open("r", encoding="utf-8") as file:
            raw_chunks = json.load(file)

        with (self.storage_dir / "config.json").open("r", encoding="utf-8") as file:
            config = json.load(file)

        self.chunks = [FireChunk(**item) for item in raw_chunks]
        self.embeddings = np.load(self.storage_dir / "embeddings.npy").astype("float32")
        self.embedding_model = load_embedding_model(config["embedding_model"])

        if len(self.chunks) != len(self.embeddings):
            raise RuntimeError("El número de chunks y embeddings no coincide.")

    def _metadata_matches(self, metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Comprueba filtros exactos y rangos de fecha sobre un chunk."""
        aliases = {
            "date": "document_date",
            "fecha": "document_date",
            "location": "location",
            "ubicacion": "location",
            "province": "province",
            "provincia": "province",
            "community": "autonomous_community",
            "comunidad": "autonomous_community",
            "state": "state",
            "estado": "state",
        }

        for raw_key, expected in filters.items():
            if expected is None or expected == "":
                continue

            if raw_key in {"date_from", "fecha_desde"}:
                current = parse_iso_date(metadata["document_date"])
                if current < parse_iso_date(str(expected)):
                    return False
                continue

            if raw_key in {"date_to", "fecha_hasta"}:
                current = parse_iso_date(metadata["document_date"])
                if current > parse_iso_date(str(expected)):
                    return False
                continue

            key = aliases.get(raw_key, raw_key)
            current_value = metadata.get(key)

            if key == "location":
                # Para ubicación usamos coincidencia parcial: "Soneja" encontrará
                # "SONEJA", y "Empordà" encontrará "BISBAL D' EMPORDÀ, LA".
                if normalize_for_match(str(expected)) not in normalize_for_match(str(current_value)):
                    return False
            else:
                if normalize_for_match(str(current_value)) != normalize_for_match(str(expected)):
                    return False

        return True

    def search(
        self,
        query: str | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """Busca por metadatos, semántica o ambas cosas.

        - Solo metadatos: query=None y filters con valores.
        - Solo semántica: query con texto y filters=None.
        - Híbrida: primero filtra metadatos y después ordena por coseno.
        """
        filters = filters or {}

        candidate_indices = [
            index
            for index, chunk in enumerate(self.chunks)
            if self._metadata_matches(chunk.metadata, filters)
        ]

        if not candidate_indices:
            return []

        # Búsqueda puramente estructurada: devuelve los registros filtrados.
        if not query or not query.strip():
            selected = candidate_indices[:top_k]
            return [
                {
                    "score": None,
                    "chunk_id": self.chunks[index].chunk_id,
                    "text": self.chunks[index].text,
                    "metadata": self.chunks[index].metadata,
                }
                for index in selected
            ]

        # El modelo ya devuelve vectores normalizados. El producto escalar entre
        # vectores normalizados equivale a la similitud del coseno.
        query_vector = self.embedding_model.encode(
            [query],
            normalize_embeddings=True,
        ).astype("float32")[0]

        candidate_matrix = self.embeddings[candidate_indices]
        scores = candidate_matrix @ query_vector
        order = np.argsort(scores)[::-1]

        results: list[dict[str, Any]] = []
        for relative_index in order:
            score = float(scores[relative_index])
            if min_score is not None and score < min_score:
                continue

            absolute_index = candidate_indices[int(relative_index)]
            chunk = self.chunks[absolute_index]
            results.append(
                {
                    "score": score,
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                }
            )

            if len(results) >= top_k:
                break

        return results

    @staticmethod
    def build_context(results: Iterable[dict[str, Any]]) -> str:
        """Convierte los resultados recuperados en contexto trazable para el LLM."""
        blocks: list[str] = []
        for number, result in enumerate(results, start=1):
            metadata = result["metadata"]
            blocks.append(
                "\n".join(
                    [
                        f"[FUENTE {number}]",
                        f"Fecha: {metadata.get('document_date')}",
                        f"Ubicación: {metadata.get('location')}",
                        f"Provincia: {metadata.get('province')}",
                        f"Comunidad: {metadata.get('autonomous_community')}",
                        f"Documento: {metadata.get('source')}",
                        result["text"],
                    ]
                )
            )

        return "\n\n".join(blocks)

    def answer_with_ollama(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
        min_score: float | None = None,
        ollama_model: str = DEFAULT_OLLAMA_MODEL,
        ollama_host: str = DEFAULT_OLLAMA_HOST,
    ) -> dict[str, Any]:
        """Recupera contexto y pide a Ollama que redacte una respuesta fundamentada."""
        results = self.search(
            query=question,
            filters=filters,
            top_k=top_k,
            min_score=min_score,
        )

        if not results:
            return {
                "answer": "No se encontraron incendios que cumplan los filtros o la consulta.",
                "sources": [],
            }

        context = self.build_context(results)

        system_prompt = (
            "Eres un asistente especializado en partes de incendios forestales de MITECO. "
            "Responde únicamente con el contexto recuperado. No inventes datos. "
            "Si el contexto no permite responder, indícalo. "
            "Cuando cites hechos, menciona al menos la ubicación y la fecha del parte."
        )
        user_prompt = f"CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}"

        from ollama import Client

        client = Client(host=ollama_host)
        response = client.chat(
            model=ollama_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0},
        )

        # Compatibilidad con distintas versiones del cliente oficial.
        try:
            answer = response.message.content
        except AttributeError:
            answer = response["message"]["content"]

        return {
            "answer": answer,
            "sources": [
                {
                    "chunk_id": result["chunk_id"],
                    "score": result["score"],
                    **result["metadata"],
                }
                for result in results
            ],
        }


# -----------------------------------------------------------------------------
# FUNCIONES DE ALTO NIVEL PARA USAR EL PROYECTO
# -----------------------------------------------------------------------------

def ingest(input_dir: str, storage_dir: str) -> None:
    """Parsea todos los PDF de la carpeta y construye el índice local."""
    chunks = parse_pdf_directory(input_dir)
    build_and_save_index(chunks, storage_dir)
    print(f"Indexados {len(chunks)} incendios en '{storage_dir}'.")


def build_filters_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Convierte los argumentos del CLI en filtros de metadatos."""
    return {
        "location": args.location,
        "province": args.province,
        "community": args.community,
        "state": args.state,
        "date": args.date,
        "date_from": args.date_from,
        "date_to": args.date_to,
    }


def add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--location", help="Ubicación, por ejemplo: Soneja")
    parser.add_argument("--province", help="Provincia, por ejemplo: Castellón")
    parser.add_argument("--community", help="Comunidad autónoma")
    parser.add_argument("--state", help="Estado: ACTIVO, CONTROLADO, ESTABILIZADO...")
    parser.add_argument("--date", help="Fecha exacta YYYY-MM-DD")
    parser.add_argument("--date-from", help="Fecha mínima YYYY-MM-DD")
    parser.add_argument("--date-to", help="Fecha máxima YYYY-MM-DD")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG manual de incendios MITECO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Parsear PDF y crear el índice")
    ingest_parser.add_argument("--input", default="data", help="Carpeta con PDF")
    ingest_parser.add_argument("--storage", default="storage", help="Carpeta del índice")

    search_parser = subparsers.add_parser("search", help="Buscar sin usar el LLM")
    search_parser.add_argument("--storage", default="storage")
    search_parser.add_argument("--query", help="Consulta semántica; omitir para solo metadatos")
    search_parser.add_argument("--top-k", type=int, default=5)
    search_parser.add_argument("--min-score", type=float)
    add_filter_arguments(search_parser)

    ask_parser = subparsers.add_parser("ask", help="Buscar y responder con Ollama")
    ask_parser.add_argument("--storage", default="storage")
    ask_parser.add_argument("--question", required=True)
    ask_parser.add_argument("--top-k", type=int, default=5)
    ask_parser.add_argument("--min-score", type=float)
    ask_parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL)
    ask_parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    add_filter_arguments(ask_parser)

    args = parser.parse_args()

    if args.command == "ingest":
        ingest(args.input, args.storage)
        return

    rag = ManualFireRAG(args.storage)
    filters = build_filters_from_args(args)

    if args.command == "search":
        results = rag.search(
            query=args.query,
            filters=filters,
            top_k=args.top_k,
            min_score=args.min_score,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if args.command == "ask":
        response = rag.answer_with_ollama(
            question=args.question,
            filters=filters,
            top_k=args.top_k,
            min_score=args.min_score,
            ollama_model=args.ollama_model,
            ollama_host=args.ollama_host,
        )
        print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
