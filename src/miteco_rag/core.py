# ---------------
# IMPORTS
# ---------------
import chromadb
from chromadb import Collection
from chromadb.api import ClientAPI

from pathlib import Path
from sentence_transformers import SentenceTransformer

from query_filters import MetadataCatalog

import sqlite3
from metadata_store import METADATA_DB_PATH, connect_metadata_db

# -----------------
# CONSTANTES
# -----------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROMA_PATH = Path(PROJECT_ROOT, 'data', 'chroma')
COLLECTION_NAME = 'MITECO_fire_snapshots'
EMBEDDING_MODEL = 'BAAI/bge-m3' 

# -----------------
# FUNCIONES
# -----------------
def load_chroma() -> tuple[ClientAPI, Collection]:
   '''
   Abre Chroma y devuelve el cliente junto a la colección
   '''
   db_client = chromadb.PersistentClient(path = CHROMA_PATH)
   db_collection = db_client.get_collection(
        name = COLLECTION_NAME,
        embedding_function = None
    )
   return db_client, db_collection

def load_metadata_connection() -> sqlite3.Connection:
    if not METADATA_DB_PATH.is_file():
        raise FileNotFoundError('No existe la base SQLite de metadatos.')
    return connect_metadata_db(METADATA_DB_PATH)

def loader()-> tuple[SentenceTransformer, ClientAPI, Collection, MetadataCatalog]:
    model = SentenceTransformer(EMBEDDING_MODEL, device = 'cpu')

    client, collection = load_chroma()

    records = collection.get(
        include = ['metadatas']
    )
    catalog = MetadataCatalog.from_metadatas(records['metadatas'])

    return model, client, collection, catalog