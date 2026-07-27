# ---------------
# IMPORTS
# ---------------
from sentence_transformers import SentenceTransformer
from chromadb.api.types import QueryResult
from chromadb import Collection

# -----------------
# FUNCIONES
# -----------------

def retrieve(
        query: str, 
        model: SentenceTransformer, 
        collection: Collection,
        where: dict[str, object] | None,  
        top_k: int = 10
    ) -> QueryResult:
    '''
    Extrae los chuncks más similares a la query de entrada y devuelve sus metadatos y embeddings.
    '''
    query_embedding = model.encode(
        query, 
        #batch_size = 8,
        #show_progress_bar = True,
        normalize_embeddings = True,    
    )

    query_args = {
        'query_embeddings': [query_embedding.tolist()],
        'n_results': top_k,
        'include': ['documents','metadatas', 'distances'],
    }

    if where is not None:
        query_args['where'] = where
        
    retrieval_context = collection.query(**query_args)

    return retrieval_context

