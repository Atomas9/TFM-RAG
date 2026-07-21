from pathlib import Path

import chromadb


CHROMA_PATH = Path("data/chroma")

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

print(client.list_collections())

collection = client.get_collection(
    name="MITECO_fire_snapshots",
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