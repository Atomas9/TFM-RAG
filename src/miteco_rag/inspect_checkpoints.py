from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

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
        history = list(
            checkpointer.list(config)
        )

        if not history:
            print(
                "No se encontraron checkpoints "
                "para esa conversación."
            )
            return

        # ``SqliteSaver.list()`` devuelve primero los checkpoints más
        # recientes. Los invertimos para mostrarlos en orden cronológico.
        for checkpoint_tuple in reversed(history):
            checkpoint = checkpoint_tuple.checkpoint
            metadata = checkpoint_tuple.metadata
            values = checkpoint.get("channel_values", {})

            print("\n---------------------")
            print(
                "Paso:",
                metadata.get("step"),
            )
            print(
                "Canales actualizados:",
                checkpoint.get("updated_channels", []),
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
