"""Интерактивный цикл общения с агентом."""

import uuid
from typing import TYPE_CHECKING

from langchain.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

if TYPE_CHECKING:
    from pydantic import BaseModel

EXIT_COMMANDS = {"exit", "quit"}


def run(agent: CompiledStateGraph) -> None:

    print("Агент scenarAIst готов. Введите 'exit' или 'quit' для выхода.\n")

    while True:
        # TODO input() блокирует выполнение и не поддерживает Ctrl+C корректно
        # в некоторых окружениях. Рекомендуется: использовать асинхронный ввод
        # или обработку сигналов.
        text = input("> ").strip()

        if not text:
            continue

        if text.lower() in EXIT_COMMANDS:
            print("До свидания!")
            break

        config: dict[str, dict[str, str]] = {
            "configurable": {
                "thread_id": uuid.uuid4().hex,
            }
        }

        # ? agent.invoke не обрабатывает возможные ошибки LLM (timeout, rate limit, некорректный ответ).
        # Рекомендуется: добавить retry-логику с exponential backoff.
        # ? result["messages"][-1] — берётся последнее сообщение, но в
        # истории могут быть ToolMessage или SystemMessage.
        # Рекомендуется: фильтровать по AIMessage или проверять тип.
        result = agent.invoke(input={"messages": [HumanMessage(content=text)]}, config=config)
        response: BaseModel = result["response"]
        print(response.model_dump_json(indent=2, ensure_ascii=False))
