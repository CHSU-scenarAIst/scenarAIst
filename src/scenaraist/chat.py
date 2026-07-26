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

    config: dict[str, dict[str, str]] = {
        "configurable": {
            "thread_id": uuid.uuid4().hex,
        }
    }

    while True:
        # TODO input() блокирует выполнение и не поддерживает Ctrl+C корректно
        # в некоторых окружениях. Рекомендуется: использовать асинхронный ввод
        # или обработку сигналов.
        content = input("> ").strip()

        if not content:
            continue

        if content.lower() in EXIT_COMMANDS:
            print("До свидания!")
            break

        result = agent.invoke(input={"messages": [HumanMessage(content)]}, config=config)
        response: BaseModel = result["response"]
        answer = response.model_dump_json(indent=2, ensure_ascii=False)
        print(answer)
