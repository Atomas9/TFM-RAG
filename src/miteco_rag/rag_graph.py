from typing import TypedDict, Literal
from chromadb import Collection
from sentence_transformers import SentenceTransformer

from core import loader
from bouncer import BouncerDecision, bouncer
from query_filters import DeterministicAnalysis, MetadataCatalog, build_deterministic_analysis
from revisor_query_filters import FilterReview, revisor
from generate_filter_LLM import FilterProposal, generate_filter_llm, resolve_final_where
from retrieval_chroma import retrieve
from augmented_generator import generate_context, generate_answer 

from chromadb.api.types import QueryResult
from langgraph.graph import END, START, StateGraph
from functools import partial

class GraphState(TypedDict, total = False):
    """Información que los nodos comparten durante una ejecución."""
    query: str
    decision: BouncerDecision
    analysis: DeterministicAnalysis
    review: FilterReview
    proposal: FilterProposal
    deterministic_where: dict[str, object] | None
    final_where: dict[str, object] | None
    raw_context: QueryResult
    context: str
    answer: str


# ------------------
# NODOS
# ------------------
def bouncer_node(state: GraphState):
    decision = bouncer(state['query'])
    result = {'decision': decision}
    if decision.decision == 'NO GO':
        result['answer'] = 'Pregunta no relacionada con incendios'

    return result


def deterministic_analysis_node(state: GraphState, catalog: MetadataCatalog):
    analysis = build_deterministic_analysis(state['query'], catalog)
    result = {
        'analysis': analysis,
        'deterministic_where': analysis.deterministic_where
    }
    return result

def reviewer_node(state: GraphState):
    review = revisor(state['query'], state['analysis'])
    result = {'review': review}
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
    proposal = generate_filter_llm(
        state['query'], 
        state['analysis'], 
        state['review'], 
        catalog)
    result = {'proposal': proposal}
    return result

def resolve_where_node(state: GraphState):
    where = resolve_final_where(
        state['analysis'],
        state['review'],
        state['proposal']
        )
    result = {'final_where': where}
    return result

def retrieve_node(state: GraphState, 
                  emb_model: SentenceTransformer,
                  collection: Collection,
                  top_k: int = 10):
    raw_context = retrieve(state['query'], emb_model, collection, state['final_where'], top_k)
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
    if state['decision'].decision == 'GO':
        return 'continue'
    else:
        return 'end'

def route_after_reviewer(state: GraphState) -> Literal['generate', 'keep', 'end']:
    action = state['review'].action
    if action in {'extend', 'replace'}:
        return 'generate'
    elif action == 'keep':
        return 'keep'
    else:
        return 'end'



def create_graph(checkpointer):
    emb_model, collection, catalog = loader()
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

    graph = StateGraph(GraphState)

    graph.add_node('Bouncer', bouncer_node)
    graph.add_node('DeterministicAnalysis', deterministic_analysis_node_conf)
    graph.add_node('Reviewer', reviewer_node)
    graph.add_node('GenerateFilter', generate_filter_node_conf)
    graph.add_node('ResolveWhere', resolve_where_node)
    graph.add_node('Retrieve', retrieve_node_conf)
    graph.add_node('GenerateContext', context_node)
    graph.add_node('GenerateAnswer', generate_answer_node)

    graph.add_edge(START, 'Bouncer')
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
            'keep': 'Retrieve',
            'end': END
        }
    )
    graph.add_edge('GenerateFilter', 'ResolveWhere')
    graph.add_edge('ResolveWhere', 'Retrieve')
    graph.add_edge('Retrieve', 'GenerateContext')
    graph.add_edge('GenerateContext', 'GenerateAnswer')
    graph.add_edge('GenerateAnswer', END)

    return graph.compile(checkpointer = checkpointer)

