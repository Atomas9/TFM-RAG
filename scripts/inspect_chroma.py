from pathlib import Path

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "MITECO_fire_snapshots"

def main() -> None:
    """Muestra el tamaño y tres registros de la colección local de Chroma."""

    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        print("Colecciones:", client.list_collections())

        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=None,
        )

        print("Registros:", collection.count())
        results = collection.peek(limit=3)

        for identifier, document, metadata in zip(
            results["ids"],
            results["documents"],
            results["metadatas"],
        ):
            print("-" * 50)
            print("ID:", identifier)
            print("Documento:")
            print(document)
            print("Metadatos:")
            print(metadata)
    finally:
        client.close()


if __name__ == "__main__":
    main()
