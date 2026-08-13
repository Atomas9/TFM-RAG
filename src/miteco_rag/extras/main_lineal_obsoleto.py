"""Flujo lineal histórico anterior a la integración completa en LangGraph.

Este archivo se conserva como referencia académica. Está desactualizado y no
debe utilizarse como punto de entrada del MVP.
"""

from core import loader
from bouncer import bouncer
from query_filters import build_deterministic_analysis
from revisor_query_filters import revisor
from generate_filter_LLM import generate_filter_llm, resolve_final_where
from retrieval_chroma import retrieve
from augmented_generator import generate_context, generate_answer 





def main() -> None:
    emb_model, collection, catalog = loader()

    query = input('Escribe tu pregunta: ')
    decision = bouncer(query)
    if decision.decision == 'NO GO':
        print('\nPregunta no relacionada con incendios')
        return
    analysis = build_deterministic_analysis(query, catalog)
    where = analysis.deterministic_where
    review = revisor(query, analysis)
    if review.action == 'clarify':
        print('\nLa consulta necesita una aclaración:\n')
        for issue in review.issues:
            print(f'- {issue}')
        return
    elif review.action in {'extend', 'replace'}:
        proposal = generate_filter_llm(query, analysis, review, catalog)
        where =  resolve_final_where(analysis, review, proposal)

    raw_context = retrieve(query, emb_model, collection, where, top_k = 10)
    context = generate_context(raw_context)
    answer = generate_answer(query, context, where)

    print('\nRespuesta:\n')
    print(answer)

    '''
    print("\nRevisión del filtro:\n")
    print(
        review.model_dump_json(indent=2)
    )

    if review.action in {"extend", "replace"}:
        proposal = generate_filter_llm(
            query=query,
            analysis=analysis,
            review=review,
            catalog=catalog,
        )

        print("\nPropuesta del nuevo filtro:\n")
        print(
            proposal.model_dump_json(indent=2)
        )
    else:
        print(
            "\nNo es necesario generar un filtro nuevo. "
            f"Acción: {review.action}"
        )
    '''


if __name__ == '__main__':
    main()
