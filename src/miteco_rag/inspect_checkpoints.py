from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from rag_graph import create_graph


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHECKPOINT_PATH = (
    PROJECT_ROOT
    / "data"
    / "checkpoints"
    / "langgraph.sqlite"
)


def main() -> None:
    conversation_id = input(
        "Escribe el ID de la conversación: "
    ).strip()

    if not conversation_id:
        print("El ID de conversación no puede estar vacío.")
        return

    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }

    with SqliteSaver.from_conn_string(
        str(CHECKPOINT_PATH)
    ) as checkpointer:

        graph = create_graph(checkpointer)

        history = list(
            graph.get_state_history(config)
        )

        if not history:
            print(
                "No se encontraron checkpoints "
                "para esa conversación."
            )
            return

        for snapshot in reversed(history):
            values = snapshot.values

            print("\n---------------------")
            print(
                "Paso:",
                snapshot.metadata.get("step"),
            )
            print(
                "Siguiente nodo:",
                snapshot.next,
            )

            if "decision" in values:
                print("Decisión:", values["decision"])

            if "review" in values:
                print("Revisión:", values["review"])

            if "deterministic_where" in values:
                print(
                    "Filtro determinista:",
                    values["deterministic_where"],
                )

            if "final_where" in values:
                print(
                    "Filtro final:",
                    values["final_where"],
                )

            if "answer" in values:
                print("Respuesta:", values["answer"])


if __name__ == "__main__":
    main()
