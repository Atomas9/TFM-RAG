# -----------------
# IMPORTS
# -----------------
import chromadb

from pathlib import Path
from sentence_transformers import SentenceTransformer
from parseo_y_chuncking import FireSnapshot

# -----------------
# CONSTANTES
# -----------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS_PATH = Path(PROJECT_ROOT, 'data', 'processed', 'fire_snapshots.jsonl')
CHROMA_PATH = Path(PROJECT_ROOT, 'data', 'chroma')
COLLECTION_NAME = 'MITECO_fire_snapshots'
EMBEDDING_MODEL = 'BAAI/bge-m3' 


# -----------------
# FUNCTIONS
# -----------------
def load_snapshots(path: Path ) -> list[FireSnapshot]:
    '''
    Carga cada snapshot desde el archivo JSONL
    '''
    snapshots: list[FireSnapshot] = []
    with path.open('r', encoding = 'utf-8') as file:
        for line in file:
            if not line.strip():
                continue
            snapshot = FireSnapshot.model_validate_json(line)
            snapshots.append(snapshot)
    
    return snapshots

def snapshot_to_metadata(snapshot: FireSnapshot) -> dict:
    '''
    Convierte cada snapshot en metadatos para ChromaDB
    '''
    metadata = {
        "document_id": snapshot.document_id,
        "incident_key": snapshot.incident_key,
        "country": snapshot.country,
        "autonomous_community": snapshot.autonomous_community,
        "autonomous_community_normalized":
            snapshot.autonomous_community_normalized,
        "province": snapshot.province,
        "province_normalized": snapshot.province_normalized,
        "location": snapshot.location,
        "location_normalized": snapshot.location_normalized,
        "status": snapshot.status,
        "operational_status": snapshot.operational_status,
        "report_date": snapshot.report_date.isoformat(),
        "report_date_number": snapshot.report_date_number,
        "page_start": snapshot.page_start,
        "page_end": snapshot.page_end,
        "source_file": snapshot.source_file,
        "source_sha256": snapshot.source_sha256,
        "parser_version": snapshot.parser_version,
        "resource_codes": ", ".join(snapshot.resource_codes),
    }

    # Eliminamos los datos cuyo valor sea None
    return {
        key: value
        for key, value in metadata.items()
        if value is not None
    }

def main():
    snapshots = load_snapshots(SNAPSHOTS_PATH)

    # Cargamos el modelo de embeddings
    model = SentenceTransformer(EMBEDDING_MODEL, device = 'cpu')

    # Lista con los chunks de cada snapshot
    chunk_texts = [snapshot.chunk_text for snapshot in snapshots]

    # Generamos los embeddings
    embeddings = model.encode(
        chunk_texts, 
        batch_size = 8,
        show_progress_bar = True,
        normalize_embeddings = True,    
    )
    
    # Creamos la base de datos ChromaDB y la colección
    db = chromadb.PersistentClient(path = CHROMA_PATH)
    db_collection = db.get_or_create_collection(
        name = COLLECTION_NAME,
        embedding_function = None
    )

    # Preparamos los campos que espera ChromaDB
    ids = [snapshot.snapshot_id for snapshot in snapshots]
    documents = [snapshot.chunk_text for snapshot in snapshots]
    metadatas = [snapshot_to_metadata(snapshot) for snapshot in snapshots]

    # Insertamos o actualizamos los registros
    db_collection.upsert(
        ids = ids,
        embeddings = embeddings.tolist(),
        metadatas = metadatas,
        documents = documents
    )

    # Comprobaciones básicas
    print(f"Snapshots leídos: {len(snapshots)}")
    print(f"Embeddings generados: {len(embeddings)}")
    print(f"Registros en Chroma: {db_collection.count()}")
    print(f"Base de datos: {CHROMA_PATH.resolve()}")

if __name__ == '__main__':
    main()




