from rag_graph import create_graph

def main() -> None:
    graph = create_graph()
    config = {
        'configurable': {
            'thread_id': 'terminal-session'
        }
    }

    query = input('Escribe tu pregunta: ')

    state = graph.invoke(
        {'query': query},
        config = config
    )
    answer = state['answer']

    print(f'\n{answer}')

if __name__ == '__main__':
    main()
