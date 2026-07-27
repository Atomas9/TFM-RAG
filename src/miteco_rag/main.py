from core import loader
from query_filters import build_deterministic_analysis
from revisor_query_filters import revisor
# from generate_filter_LLM import
from retrieval_chroma import retrieve
from augmented_generator import generate_context, generate_answer 





def main() -> None:
    emb_model, collection, catalog = loader()

    query = input('Escribe tu pregunta: ')
    analysis = build_deterministic_analysis(query, catalog)
    where = analysis.deterministic_where
    review = revisor(query, analysis)
    raw_context = retrieve(query, emb_model, collection, where, top_k = 10)
    context = generate_context(raw_context)
    answer = generate_answer(query = query, context = context)

    print('\nRespuesta:\n')
    print(answer)


if __name__ == '__main__':
    main()
