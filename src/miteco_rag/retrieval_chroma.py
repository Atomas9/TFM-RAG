# ---------------
# IMPORTS
# ---------------
import sqlite3
from typing import Literal, TypedDict

from sentence_transformers import SentenceTransformer
from chromadb import Collection

if __package__:
    from .metadata_queries import get_extreme_snapshot_ids
else:
    from metadata_queries import get_extreme_snapshot_ids


class RetrievalResult(TypedDict):
    """Formato común de salida para todos los modos de recuperación."""

    mode: Literal["hybrid", "min_max"]
    ids: list[str]
    documents: list[str]
    metadatas: list[dict[str, object]]
    distances: list[float] | None
    aggregate: dict[str, object] | None

# -----------------
# FUNCIONES
# -----------------

def retrieve(
        query: str, 
        model: SentenceTransformer, 
        collection: Collection,
        where: dict[str, object] | None,  
        top_k: int = 10
    ) -> RetrievalResult:
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

    # Chroma devuelve una lista por cada consulta. Como aquí solo enviamos una
    # pregunta, extraemos la primera para ofrecer una salida plana y común.
    return {
        'mode': 'hybrid',
        'ids': (retrieval_context.get('ids') or [[]])[0],
        'documents': (retrieval_context.get('documents') or [[]])[0],
        'metadatas': (retrieval_context.get('metadatas') or [[]])[0],
        'distances': (retrieval_context.get('distances') or [[]])[0],
        'aggregate': None,
    }


def retrieve_min_max(
        collection: Collection,
        metadata_connection: sqlite3.Connection,
        where: dict[str, object] | None,
        operation: Literal["min", "max"],
    ) -> RetrievalResult:
    """Recupera todos los snapshots de la fecha mínima o máxima filtrada."""

    report_date, snapshot_ids = get_extreme_snapshot_ids(
        connection=metadata_connection,
        where=where,
        operation=operation,
    )

    if not snapshot_ids:
        return {
            'mode': 'min_max',
            'ids': [],
            'documents': [],
            'metadatas': [],
            'distances': None,
            'aggregate': None,
        }

    records = collection.get(
        ids=snapshot_ids,
        include=['documents', 'metadatas'],
    )

    return {
        'mode': 'min_max',
        'ids': records.get('ids') or [],
        'documents': records.get('documents') or [],
        'metadatas': records.get('metadatas') or [],
        'distances': None,
        'aggregate': {
            'operation': operation,
            'report_date_number': report_date,
        },
    }
