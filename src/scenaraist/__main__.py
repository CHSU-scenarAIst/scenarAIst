"""Точка входа для запуска агента scenarAIst как модуля."""

import logging

import questionary
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import InMemorySaver

from scenaraist.chat import run
from scenaraist.graph import build_agent
from scenaraist.model import ProviderName
from scenaraist.retriever import get_storage_retriever

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Запустить чат-бота scenarAIst."""
    LOGGER.info("Запуск СценарИИста")

    load_dotenv(override=False)

    choices = [questionary.Choice(title=p.name, value=p) for p in ProviderName]

    try:
        provider = questionary.select("Выберите провайдера чата:", choices).ask()
        chat = ProviderName(provider).get_chat()
    except Exception as e:
        LOGGER.error(f"Ошибка LLM-чата: {e}")
        raise

    try:
        provider = questionary.select("Выберите провайдера эмбеддингов:", choices).ask()
        embeddings = ProviderName(provider).get_embeddings()
    except Exception as e:
        LOGGER.error(f"Ошибка LLM-эмбеддингов: {e}")
        raise

    try:
        # TODO вынести в конфигурационный файл.
        folder_path: str = "./docs/zhopka"
        db_path: str = "rag.sqlite3"
        table = "documents"
        max_results = 5
        max_tokens = 10000
        chunk_size = 1000
        chunk_overlap = 200

        retriever = get_storage_retriever(folder_path, db_path, table, embeddings, chunk_size, chunk_overlap)
        web_search = TavilySearch(max_results=max_results, topic="general")
        tools = [web_search]
        # ? SQLite/Postgres Checkpointer
        checkpointer = InMemorySaver()

        agent = build_agent(chat, checkpointer, tools, max_tokens, retriever)
        run(agent)
    except Exception as e:
        LOGGER.error(f"Ошибка run: {e}")
        raise

    LOGGER.info("Завершение работы...")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.CRITICAL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())
