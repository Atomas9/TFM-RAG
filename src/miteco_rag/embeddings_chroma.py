# -----------------
# IMPORTS
# -----------------
import chromadb
import hashlib
import json

from chromadb import Collection
from pathlib import Path
from sentence_transformers import SentenceTransformer

if __package__:
    from .parseo_y_chuncking import FireSnapshot
else:
    from parseo_y_chuncking import FireSnapshot

# -----------------
# CONSTANTES
# -----------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS_PATH = Path(PROJECT_ROOT, 'data', 'processed', 'fire_snapshots.jsonl')
CHROMA_PATH = Path(PROJECT_ROOT, 'data', 'chroma')
COLLECTION_NAME = 'MITECO_fire_snapshots'
EMBEDDING_MODEL = 'BAAI/bge-m3' 
INDEX_VERSION = '1'


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

def build_index_signature(snapshot: FireSnapshot) -> str:
    """Identifica el contenido y la configuración usados para indexar."""

    payload = {
        'snapshot': snapshot.model_dump(mode = 'json'),
        'embedding_model': EMBEDDING_MODEL,
        'normalize_embeddings': True,
        'index_version': INDEX_VERSION,
    }
    serialized_payload = json.dumps(
        payload,
        ensure_ascii = False,
        sort_keys = True,
        separators = (',', ':'),
    )
    return hashlib.sha256(
        serialized_payload.encode('utf-8')
    ).hexdigest()

def load_existing_signatures(
        db_collection: Collection
) -> dict[str, str | None]:
    """Carga la firma guardada para cada registro existente en Chroma."""

    records = db_collection.get(include = ['metadatas'])
    ids = records.get('ids') or []
    metadatas = records.get('metadatas') or []

    return {
        snapshot_id: metadata.get('index_signature')
        for snapshot_id, metadata in zip(ids, metadatas, strict = True)
    }

def select_snapshots_to_index(
        snapshots: list[FireSnapshot],
        existing_signatures: dict[str, str | None]
) -> list[FireSnapshot]:
    """Selecciona snapshots nuevos o cuya firma haya cambiado."""

    return [
        snapshot
        for snapshot in snapshots
        if existing_signatures.get(snapshot.snapshot_id)
        != build_index_signature(snapshot)
    ]

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
        "index_signature": build_index_signature(snapshot),
    }

    # Eliminamos los datos cuyo valor sea None
    return {
        key: value
        for key, value in metadata.items()
        if value is not None
    }

def main():
    snapshots = load_snapshots(SNAPSHOTS_PATH)

    # Creamos la base de datos ChromaDB y la colección
    db = chromadb.PersistentClient(path = CHROMA_PATH)
    db_collection = db.get_or_create_collection(
        name = COLLECTION_NAME,
        embedding_function = None
    )

    existing_signatures = load_existing_signatures(db_collection)
    pending_snapshots = select_snapshots_to_index(
        snapshots,
        existing_signatures,
    )
    current_ids = {
        snapshot.snapshot_id
        for snapshot in snapshots
    }
    stale_ids = set(existing_signatures) - current_ids

    print(f"Snapshots leídos: {len(snapshots)}")
    print(f"Snapshots pendientes: {len(pending_snapshots)}")
    print(f"Registros obsoletos detectados: {len(stale_ids)}")

    if not pending_snapshots:
        print("Chroma ya está actualizado. No se carga el modelo de embeddings.")
        print(f"Registros en Chroma: {db_collection.count()}")
        print(f"Base de datos: {CHROMA_PATH.resolve()}")
        return

    # El modelo pesado solo se carga si existen registros pendientes.
    model = SentenceTransformer(EMBEDDING_MODEL, device = 'cpu')

    chunk_texts = [
        snapshot.chunk_text
        for snapshot in pending_snapshots
    ]
    embeddings = model.encode(
        chunk_texts,
        batch_size = 8,
        show_progress_bar = True,
        normalize_embeddings = True,
    )

    # Preparamos los campos que espera ChromaDB
    ids = [snapshot.snapshot_id for snapshot in pending_snapshots]
    documents = [snapshot.chunk_text for snapshot in pending_snapshots]
    metadatas = [
        snapshot_to_metadata(snapshot)
        for snapshot in pending_snapshots
    ]

    # Insertamos o actualizamos los registros
    db_collection.upsert(
        ids = ids,
        embeddings = embeddings.tolist(),
        metadatas = metadatas,
        documents = documents
    )

    # Comprobaciones básicas
    print(f"Embeddings generados: {len(embeddings)}")
    print(f"Registros en Chroma: {db_collection.count()}")
    print(f"Base de datos: {CHROMA_PATH.resolve()}")

if __name__ == '__main__':
    main()


