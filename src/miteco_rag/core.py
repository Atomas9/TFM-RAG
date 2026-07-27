# ---------------
# IMPORTS
# ---------------
import chromadb
from chromadb import Collection

from pathlib import Path
from sentence_transformers import SentenceTransformer

from query_filters import MetadataCatalog

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
def load_chroma_collection() -> Collection:
   '''
   carga la colección de ChromaDB desde el path especificado
   '''
   db = chromadb.PersistentClient(path = CHROMA_PATH)
   db_collection = db.get_collection(
        name = COLLECTION_NAME,
        embedding_function = None
    )
   return db_collection

def loader()-> tuple[SentenceTransformer, Collection, MetadataCatalog]:
    model = SentenceTransformer(EMBEDDING_MODEL, device = 'cpu')

    collection = load_chroma_collection()

    records = collection.get(
        include = ['metadatas']
    )
    catalog = MetadataCatalog.from_metadatas(records['metadatas'])
    return model, collection, catalog