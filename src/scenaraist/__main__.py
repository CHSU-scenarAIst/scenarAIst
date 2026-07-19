"""Точка входа для запуска агента scenarAIst как модуля."""

import logging
from typing import Any

import questionary
from dotenv import load_dotenv
from langchain.messages import AnyMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from scenaraist.loader import iter_documents, iter_splits
from scenaraist.model import get_chat_model, get_embeddings

# from .db import make_db
from .graph import build_agent

EXIT_COMMANDS = {"exit", "quit"}
LOGGER = logging.getLogger(__name__)

CHOICES = [
    questionary.Choice("GigaChat", value="gigachat"),
    questionary.Choice("OpenRouter", value="openrouter"),
    questionary.Choice("OpenAI", value="openai"),
    questionary.Choice("HuggingFace", value="huggingface"),
]


def main() -> int:
    """Запустить чат-бота scenarAIst."""

    LOGGER.info("Запуск СценарИИста")
    load_dotenv(override=False)

    try:
        provider = questionary.select("Выберите провайдера чата:", choices=CHOICES).ask()
        chat = get_chat_model(provider)
    except Exception as e:
        LOGGER.error(f"Ошибка LLM-чата: {e}")
        return 1

    try:
        provider = questionary.select("Выберите провайдера эмбеддингов:", choices=CHOICES).ask()
        embeddings = get_embeddings(provider)
    except Exception as e:
        LOGGER.error(f"Ошибка LLM-эмбеддингов: {e}")
        return 1

    agent = build_agent(chat)
    run(agent)

    LOGGER.info("Завершение работы...")
    return 0


# TODO заглушка
CONFIG = {
    "configurable": {
        "thread_id": "user-1",
    }
}


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
            result = agent.invoke({"messages": [HumanMessage(content=text)]}, config=CONFIG)

            # TODO История сообщений растёт бесконечно — каждое взаимодействие добавляет
            # HumanMessage, AIMessage и возможные ToolMessage. Нет механизма очистки или
            # сокращения контекста, что может привести к превышению лимита контекста LLM.
            history = result["messages"]

            # TODO В LangChain AIMessage.content может быть как строкой, так и
            # списком блоков контента (например, при использовании мультимодальных моделей).
            response = history[-1].content

            print(response)
        except Exception as e:
            print(f"Ошибка: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())

    folder_path = "./docs/weather"
    documents = iter_documents(folder_path)

    i = 0
    for _ in iter_splits(documents):
        # vectorstore.add_documents([chunk])
        i += 1
    print(f"Loaded {i} chunks from the folder.")

    # TODO
    # make_db()
