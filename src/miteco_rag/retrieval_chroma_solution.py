"""Recuperacion semantica e hibrida sobre la coleccion de MITECO."""

# -----------------
# IMPORTS
# -----------------
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

try:
    # Importacion usada al ejecutar el modulo como paquete.
    from .query_filters import (
        MetadataCatalog,
        ParsedQuery,
        build_chroma_where,
        parse_metadata_filters,
    )
except ImportError:
    # Importacion usada por el boton Play de VS Code sobre este archivo.
    from query_filters import (
        MetadataCatalog,
        ParsedQuery,
        build_chroma_where,
        parse_metadata_filters,
    )


# -----------------
# CONSTANTES
# -----------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "MITECO_fire_snapshots"
EMBEDDING_MODEL = "BAAI/bge-m3"


# -----------------
# FUNCIONES
# -----------------
def load_chroma_collection():
    """Abre la coleccion persistente creada durante la indexacion."""

    db = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return db.get_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
    )


def load_metadata_catalog(db_collection) -> MetadataCatalog:
    """Obtiene los valores consultables a partir de Chroma."""

    records = db_collection.get(include=["metadatas"])
    metadatas = records.get("metadatas") or []
    return MetadataCatalog.from_metadatas(metadatas)


def retrieve(
    query: str,
    top_k: int = 10,
    where: dict[str, object] | None = None,
    *,
    db_collection=None,
    model: SentenceTransformer | None = None,
) -> dict:
    """Ejecuta una busqueda vectorial, opcionalmente limitada por ``where``."""

    if not query.strip():
        raise ValueError("La consulta no puede estar vacia.")
    if top_k < 1:
        raise ValueError("top_k debe ser mayor o igual que 1.")

    if db_collection is None:
        db_collection = load_chroma_collection()
    if model is None:
        model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")

    query_embedding = model.encode(
        query,
        normalize_embeddings=True,
    )

    query_arguments = {
        "query_embeddings": [query_embedding.tolist()],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where is not None:
        query_arguments["where"] = where

    return db_collection.query(**query_arguments)


def retrieve_with_filters(
    query: str,
    top_k: int = 10,
    *,
    db_collection=None,
    model: SentenceTransformer | None = None,
) -> tuple[dict, ParsedQuery, dict[str, object] | None]:
    """Interpreta la pregunta y ejecuta retrieval semantico con metadatos.

    Se devuelven los resultados, la interpretacion completa y el ``where``.
    Esto permite inspeccionar por separado que entendio el analizador y que
    condicion recibio finalmente Chroma.
    """

    if db_collection is None:
        db_collection = load_chroma_collection()

    catalog = load_metadata_catalog(db_collection)
    parsed_query = parse_metadata_filters(query, catalog)

    if parsed_query.ambiguities:
        details = " ".join(parsed_query.ambiguities)
        raise ValueError(f"Consulta ambigua: {details}")

    where = build_chroma_where(parsed_query.filters)
    results = retrieve(
        query=parsed_query.semantic_query,
        top_k=top_k,
        where=where,
        db_collection=db_collection,
        model=model,
    )
    return results, parsed_query, where


def print_retrieval_results(results: dict) -> None:
    """Muestra de forma legible los resultados de una sola consulta."""

    ids = results.get("ids", [[]])[0]
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    if not ids:
        print("No se encontraron snapshots para los filtros detectados.")
        return

    for position, (identifier, document, metadata, distance) in enumerate(
        zip(ids, documents, metadatas, distances),
        start=1,
    ):
        print("=" * 70)
        print(f"Resultado {position}")
        print(f"ID: {identifier}")
        print(f"Distancia: {distance:.4f}")
        print(f"Localizacion: {metadata.get('location')}")
        print(f"Provincia: {metadata.get('province')}")
        print(f"Fecha: {metadata.get('report_date')}")
        print(f"Estado: {metadata.get('status')}")
        print("Chunk:")
        print(document)


def main() -> None:
    """Ejemplo manual de recuperacion hibrida."""

    query = "Hay incendios activos en Leon?"
    results, parsed_query, where = retrieve_with_filters(query, top_k=5)

    print("Pregunta:", query)
    print(
        "Filtros detectados:",
        parsed_query.filters.model_dump(exclude_defaults=True),
    )
    print("Where de Chroma:", where)
    print_retrieval_results(results)


if __name__ == "__main__":
    main()
