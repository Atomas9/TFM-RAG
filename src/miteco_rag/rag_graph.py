from typing import TypedDict, Literal, Annotated
from operator import add
from chromadb import Collection
from sentence_transformers import SentenceTransformer
import sqlite3

from prepare_turn import ChatMessage, prepare_turn
from rewrite_query import rewrite_query
from bouncer import bouncer
from query_filters import DeterministicAnalysis, MetadataCatalog, build_deterministic_analysis
from revisor_query_filters import FilterReview, revisor
from generate_filter_LLM import FilterProposal, generate_filter_llm, resolve_final_where
from retrieval_mode import RetrievalMode, choose_retrieval_mode
from retrieval_chroma import RetrievalResult, retrieve, retrieve_min_max, retrieve_count
from augmented_generator import generate_context, generate_answer 

from langgraph.graph import END, START, StateGraph
from functools import partial

class GraphState(TypedDict, total = False):
    """Información que los nodos comparten durante una ejecución."""
    messages: Annotated[list[ChatMessage], add]
    user_query: str
    query: str
    decision: Literal["GO", "NO GO"] | None
    analysis: dict[str, object] | None
    review: dict[str, object] | None
    proposal: dict[str, object] | None
    deterministic_where: dict[str, object] | None
    final_where: dict[str, object] | None
    retrieval_mode: dict[str, object] | None
    raw_context: RetrievalResult | None
    context: str
    answer: str


# ------------------
# NODOS
# ------------------
def prepare_turn_node(state: GraphState):
    result = prepare_turn(state['messages'])
    return result

def rewrite_query_node(state: GraphState):
    rewritten_query = rewrite_query(state['messages'])
    result = {'query': rewritten_query}
    return result

def bouncer_node(state: GraphState):
    response = bouncer(state['query'])
    decision = response.decision
    result = {'decision': decision}
    if decision == 'NO GO':
        result['answer'] = 'Pregunta no relacionada con incendios'

    return result


def deterministic_analysis_node(state: GraphState, catalog: MetadataCatalog):
    analysis = build_deterministic_analysis(state['query'], catalog)
    result = {
        'analysis': analysis.model_dump(mode = 'json'),
        'deterministic_where': analysis.deterministic_where
    }
    return result

def reviewer_node(state: GraphState):
    analysis = DeterministicAnalysis.model_validate(state['analysis'])
    review = revisor(state['query'], analysis)
    result = {'review': review.model_dump(mode = 'json')}
    if review.action == 'clarify':
        issues = '\n'.join(f'- {issue}' for issue in review.issues)
        result['answer'] = (
            'La consulta necesita una aclaración:\n'
            f'{issues}'
        )
    if review.action == 'keep':
        result['final_where'] = state['deterministic_where']

    return result

def generate_filter_node(state: GraphState, catalog: MetadataCatalog):
    analysis = DeterministicAnalysis.model_validate(state['analysis'])
    review = FilterReview.model_validate(state['review'])
    proposal = generate_filter_llm(
        state['query'], 
        analysis,
        review,
        catalog)
    result = {'proposal': proposal.model_dump(mode = 'json')}
    return result

def resolve_where_node(state: GraphState):
    analysis = DeterministicAnalysis.model_validate(state['analysis'])
    review = FilterReview.model_validate(state['review'])
    proposal = FilterProposal.model_validate(state['proposal'])
    where = resolve_final_where(
        analysis,
        review,
        proposal
        )
    result = {'final_where': where}
    return result

def choose_retrieval_mode_node(state: GraphState):
    retrieval_mode = choose_retrieval_mode(state['query'])
    result = {'retrieval_mode': retrieval_mode.model_dump(mode = 'json')}
    return result

def retrieve_node(state: GraphState, 
                  emb_model: SentenceTransformer,
                  collection: Collection,
                  top_k: int = 10):
    raw_context = retrieve(state['query'], emb_model, collection, state['final_where'], top_k)
    result = {'raw_context': raw_context}
    return result

def min_max_retrieve_node(state: GraphState,
                          collection: Collection,
                          metadata_connection: sqlite3.Connection):
    retrieval_mode = RetrievalMode.model_validate(state['retrieval_mode'])
    raw_context = retrieve_min_max(collection, metadata_connection, state['final_where'], retrieval_mode.operation)
    result = {'raw_context': raw_context}
    return result

def count_retrieve_node(state: GraphState,
                        metadata_connection: sqlite3.Connection):
    retrieval_mode = RetrievalMode.model_validate(state['retrieval_mode'])
    raw_context = retrieve_count(metadata_connection, state['final_where'], retrieval_mode.count_target)
    result = {'raw_context': raw_context}
    return result

def context_node(state: GraphState):
    context = generate_context(state['raw_context'])
    result = {'context': context}
    return result

def generate_answer_node(state: GraphState):
    answer = generate_answer(state['query'], state['context'], state['final_where'])
    result = {'answer': answer}
    return result

# -------------
# ROUTING LOGIC
# -------------
def route_after_bouncer(state: GraphState) -> Literal['continue', 'end']:
    if state['decision'] == 'GO':
        return 'continue'
    else:
        return 'end'

def route_after_reviewer(state: GraphState) -> Literal['generate', 'keep', 'end']:
    action = state['review']['action']
    if action in {'extend', 'replace'}:
        return 'generate'
    elif action == 'keep':
        return 'keep'
    else:
        return 'end'

def route_after_retrieval_mode(state: GraphState):
    mode = state['retrieval_mode']['mode']
    if mode == 'hybrid':
        return 'hybrid'
    elif mode == 'min_max':
        return 'min_max'
    elif mode == 'count':
        return 'count'



def create_graph(
        checkpointer,
        emb_model: SentenceTransformer,
        collection: Collection,
        catalog: MetadataCatalog,
        metadata_connection: sqlite3.Connection
):
    top_k = 10
    deterministic_analysis_node_conf = partial(
        deterministic_analysis_node,
        catalog = catalog
    )
    generate_filter_node_conf = partial(
        generate_filter_node,
        catalog = catalog
    )
    retrieve_node_conf = partial(
        retrieve_node,
        emb_model = emb_model,
        collection = collection,
        top_k = top_k
    )

    min_max_retrieve_node_conf = partial(
        min_max_retrieve_node,
        collection = collection,
        metadata_connection = metadata_connection
    )

    count_retrieve_node_conf = partial(
        count_retrieve_node,
        metadata_connection = metadata_connection
    )

    graph = StateGraph(GraphState)

    graph.add_node('PrepareTurn', prepare_turn_node)
    graph.add_node('RewriteQuery', rewrite_query_node)
    graph.add_node('Bouncer', bouncer_node)
    graph.add_node('DeterministicAnalysis', deterministic_analysis_node_conf)
    graph.add_node('Reviewer', reviewer_node)
    graph.add_node('GenerateFilter', generate_filter_node_conf)
    graph.add_node('ResolveWhere', resolve_where_node)
    graph.add_node('RetrievalMode', choose_retrieval_mode_node)
    graph.add_node('Retrieve', retrieve_node_conf)
    graph.add_node('MinMaxRetrieve', min_max_retrieve_node_conf)
    graph.add_node('CountRetrieve', count_retrieve_node_conf)
    graph.add_node('GenerateContext', context_node)
    graph.add_node('GenerateAnswer', generate_answer_node)

    graph.add_edge(START, 'PrepareTurn')
    graph.add_edge('PrepareTurn', 'RewriteQuery')
    graph.add_edge('RewriteQuery', 'Bouncer')
    graph.add_conditional_edges(
        'Bouncer', 
        route_after_bouncer,
        {
            'continue': 'DeterministicAnalysis',
            'end': END
        }
        )
    graph.add_edge('DeterministicAnalysis', 'Reviewer')
    graph.add_conditional_edges(
        'Reviewer',
        route_after_reviewer,
        {
            'generate': 'GenerateFilter',
            'keep': 'RetrievalMode',
            'end': END
        }
    )
    graph.add_edge('GenerateFilter', 'ResolveWhere')
    graph.add_edge('ResolveWhere', 'RetrievalMode')
    graph.add_conditional_edges(
        'RetrievalMode',
        route_after_retrieval_mode,
        {
            'hybrid': 'Retrieve',
            'min_max': 'MinMaxRetrieve',
            'count': 'CountRetrieve'
        }
    )
    graph.add_edge('Retrieve', 'GenerateContext')
    graph.add_edge('MinMaxRetrieve', 'GenerateContext')
    graph.add_edge('CountRetrieve', 'GenerateContext')
    graph.add_edge('GenerateContext', 'GenerateAnswer')
    graph.add_edge('GenerateAnswer', END)

    return graph.compile(checkpointer = checkpointer)
