# ---------------
# IMPORTS
# ---------------
import chromadb

from pathlib import Path
from sentence_transformers import SentenceTransformer

# -----------------
# CONSTANTES
# -----------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS_PATH = Path(PROJECT_ROOT, 'data', 'processed', 'fire_snapshots.jsonl')
CHROMA_PATH = Path(PROJECT_ROOT, 'data', 'chroma')
COLLECTION_NAME = 'MITECO_fire_snapshots'
EMBEDDING_MODEL = 'BAAI/bge-m3' 

# -----------------
# FUNCIONES
# -----------------
def load_chroma_collection():
   
   '''
   carga la coleección de ChromaDB desde el path especificado
   '''
   db = chromadb.PersistentClient(path = CHROMA_PATH)
   db_collection = db.get_collection(
        name = COLLECTION_NAME,
        embedding_function = None
    )
   return db_collection


def retrieve(query: str, top_k: int = 10):
    '''
    Extrae los chuncks más similares a la query de entrada y devuelve sus metadatos y embeddings.
    '''
    model = SentenceTransformer(EMBEDDING_MODEL, device = 'cpu')
    query_embedding = model.encode(
        query, 
        #batch_size = 8,
        #show_progress_bar = True,
        normalize_embeddings = True,    
    )

    db_collection = load_chroma_collection()

    retrival_context = db_collection.query(
        query_embeddings = [query_embedding],
        n_results = top_k,
        include = ['documents','metadatas', 'distances', 'embeddings'],
    )

    return retrival_context

contexto = retrieve("Hay incendios activos en León?", top_k = 5)
print(type(contexto))

#for key, value in contexto.items():
#    print(f"{key}: {value}")

i = 0
for chunk in contexto['documents'][0]:
    i += 1
    print(f"Chunk {i}:")
    print(chunk)
