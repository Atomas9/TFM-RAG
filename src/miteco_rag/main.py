from augmented_generator import generate_answer, generate_context
from retrieval_chroma import retrieve


def main() -> None:
    query = input('Escribe tu pregunta: ')

    raw_context = retrieve(query = query, top_k = 10)
    context = generate_context(raw_context)
    answer = generate_answer(query = query, context = context)

    print('\nRespuesta:\n')
    print(answer)


if __name__ == '__main__':
    main()
