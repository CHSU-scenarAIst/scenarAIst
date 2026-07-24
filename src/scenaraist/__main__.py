"""Точка входа для запуска агента scenarAIst как модуля."""

import logging
import sqlite3
import uuid
from pathlib import Path

import questionary
import sqlite_vec
from dotenv import load_dotenv
from langchain.messages import HumanMessage
from langchain_community.vectorstores import SQLiteVec
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from scenaraist.documents import iter_documents, iter_splits
from scenaraist.graph import build_agent, format_response
from scenaraist.model import get_chat_model, get_embeddings

LOGGER = logging.getLogger(__name__)

# TODO заменить строковые провайдеры на enum
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
        raise

    try:
        provider = questionary.select("Выберите провайдера эмбеддингов:", choices=CHOICES).ask()
        embeddings = get_embeddings(provider)
    except Exception as e:
        LOGGER.error(f"Ошибка LLM-эмбеддингов: {e}")
        raise

    try:
        # TODO вынести в конфигурационный файл.
        folder_path: str = "./docs/weather"
        db_path: str = "rag.sqlite3"
        table = "documents"
        max_results = 5
        max_tokens = 8000
        chunk_size = 1000
        chunk_overlap = 200

        # TODO SQLiteVec.from_documents создаёт БД только если файл не существует.
        # При изменении модели эмбеддингов или настроек сплиттера БД не
        # пересоздаётся, что приведёт к несоответствию размерностей векторов.
        # Рекомендуется: добавить проверку версии/хеша конфигурации.
        if documents := iter_documents(folder_path) and not Path(db_path).exists():
            documents = iter_splits(documents, chunk_size, chunk_overlap)
            SQLiteVec.from_documents(
                documents=documents,
                embedding=embeddings,
                table=table,
                db_file=db_path,
            )

        web_search = TavilySearch(max_results=max_results, topic="general")
        all_tools = [format_response, web_search]
        checkpointer = InMemorySaver()
        # checkpointer = SqliteSaver.from_conn_string(state_db)

        # ? использовать пул соединений или передавать соединение через состояние графа (state).
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        db = SQLiteVec(
            table=table,
            embedding=embeddings,
            connection=conn,
        )

        retriever = db.as_retriever(search_kwargs={"k": 3})

        agent = build_agent(chat, checkpointer, all_tools, retriever, max_tokens)
        run(agent)
    except Exception as e:
        LOGGER.error(f"Ошибка: {e}")
        raise

    LOGGER.info("Завершение работы...")
    return 0


EXIT_COMMANDS = {"exit", "quit"}


def run(agent: CompiledStateGraph) -> None:
    """Запустить интерактивный цикл общения с агентом."""

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
        result = agent.invoke({"messages": [HumanMessage(content=text)]}, config=config)
        history = result["messages"][-1]
        response = history.content
        print(response)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())
