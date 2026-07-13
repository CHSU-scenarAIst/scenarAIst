"""Интерактивный цикл общения с агентом."""

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AnyMessage, HumanMessage

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


EXIT_COMMANDS = {"exit", "quit"}


logger = logging.getLogger(__name__)


def run(agent: CompiledStateGraph[Any, Any, Any, Any]) -> None:
    """Запустить интерактивный цикл общения с агентом."""
    history: list[AnyMessage] = []

    print("Агент scenarAIst готов. Введите 'exit' или 'quit' для выхода.\n")

    while True:
        try:
            text = input("> ").strip()
        except EOFError, KeyboardInterrupt:
            print("\nДо свидания!")
            break

        if not text:
            continue

        if text.lower() in EXIT_COMMANDS:
            print("До свидания!")
            break

        history.append(HumanMessage(content=text))

        try:
            logger.debug("Ввод пользователя: %s", text)

            result = agent.invoke({"messages": history})
            history = result["messages"]
            response = history[-1].content
            # TODO? Иногда content бывает не строкой (например, списком блоков контента)

            print(response)
        except Exception:
            logger.exception("Ошибка при вызове агента")
            print("Произошла ошибка. Пожалуйста, попробуйте снова.")
