"""Интерактивный цикл общения с агентом."""

from typing import Any

from langchain.messages import AnyMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

EXIT_COMMANDS = {"exit", "quit"}


def run(agent: CompiledStateGraph[Any, Any, Any, Any]) -> None:
    """Запустить интерактивный цикл общения с агентом."""
    history: list[AnyMessage] = []

    print("Агент scenarAIst готов. Введите 'exit' или 'quit' для выхода.\n")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt) as e:
            print(f"\nОшибка: {e}")
            break

        if not text:
            continue

        if text.lower() in EXIT_COMMANDS:
            print("До свидания!")
            break

        history.append(HumanMessage(content=text))

        try:
            result = agent.invoke({"messages": history})
            history = result["messages"]
            response = history[-1].content
            # TODO? Иногда content бывает не строкой (например, списком блоков контента)

            print(response)
        except Exception as e:
            print(f"Ошибка: {e}")
