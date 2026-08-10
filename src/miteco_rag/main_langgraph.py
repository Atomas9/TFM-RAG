from rag_graph import create_graph
from pathlib import Path
from uuid import uuid4
from langgraph.checkpoint.sqlite import SqliteSaver

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_PATH = (
    PROJECT_ROOT
    / 'data'
    / 'checkpoints'
    / 'langgraph.sqlite'
)

def main() -> None:
    CHECKPOINT_PATH.parent.mkdir(
        parents = True,
        exist_ok = True
    )
    conversation_id = str(uuid4())

    config = {
        'configurable': {
            'thread_id': conversation_id
        }
    }

    query = input('Escribe tu pregunta: ')

    with SqliteSaver.from_conn_string(
        str(CHECKPOINT_PATH)
    ) as checkpointer:
        graph = create_graph(checkpointer)

        state = graph.invoke(
            {'query': query},
            config = config
        )

    answer = state['answer']

    print(f'\n{answer}')
    print(f'\nID de conversación: {conversation_id}')

if __name__ == '__main__':
    main()
