# ---------------
# IMPORTS
# ---------------
import chromadb

from pathlib import Path
from sentence_transformers import SentenceTransformer

from query_filters import MetadataCatalog, metadata_query

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
def load_chroma_collection():
   '''
   carga la colección de ChromaDB desde el path especificado
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

    records = db_collection.get(
        include = ['metadatas']
    )
    catalog = MetadataCatalog.from_metadatas(records['metadatas'])
    where = metadata_query(query, catalog)

    query_args = {
        'query_embeddings': [query_embedding.tolist()],
        'n_results': top_k,
        'include': ['documents','metadatas', 'distances'],
    }

    if where is not None:
        query_args['where'] = where
        
    retrieval_context = db_collection.query(**query_args)

    return retrieval_context

def main():
    contexto = retrieve(
        '¿Qué incendios hay en León y Palencia?',
        top_k=10,
    )

    for chunk in contexto["documents"][0]:
        print(chunk)


if __name__ == "__main__":
    main()
