"""Точка входа для запуска агента scenarAIst как модуля."""

import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import questionary
import sqlite_vec
from dotenv import load_dotenv
from langchain.embeddings import Embeddings
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.vectorstores import SQLiteVec
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_tavily import TavilySearch
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.memory import InMemorySaver

from scenaraist.chat import run
from scenaraist.graph import build_agent
from scenaraist.model import ProviderName

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
        # checkpointer = SqliteSaver.from_conn_string(state_db)
        checkpointer = InMemorySaver()

        agent = build_agent(chat, checkpointer, tools, max_tokens, retriever)
        run(agent)
    except Exception as e:
        LOGGER.error(f"Ошибка run: {e}")
        raise

    LOGGER.info("Завершение работы...")
    return 0


def iter_documents(path: str, chunk_size: int, chunk_overlap: int) -> Iterator[Document]:
    """Загрузить чанки документов из указанной директории."""

    load = DirectoryLoader(
        path=path,
        glob=("*.txt", "*.docx", "*.pdf", "*.md", "*.csv", "*.xls", "*.xlsx"),
        recursive=True,
        show_progress=True,
    )

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    for document in load.lazy_load():
        yield from text_splitter.split_documents([document])


def get_storage_retriever(
    folder_path: str,
    db_path: str,
    table: str,
    embeddings: Embeddings,
    chunk_size: int,
    chunk_overlap: int,
) -> BaseRetriever:
    """Получить ретриever для SQLiteVec."""
    # TODO SQLiteVec.from_documents создаёт БД только если файл не существует.
    # При изменении модели эмбеддингов или настроек сплиттера БД не
    # пересоздаётся, что приведёт к несоответствию размерностей векторов.
    # Рекомендуется: добавить проверку версии/хеша конфигурации.
    if not Path(db_path).exists():
        documents = iter_documents(folder_path, chunk_size, chunk_overlap)
        SQLiteVec.from_documents(
            documents=documents,
            embedding=embeddings,
            table=table,
            db_file=db_path,
        )

    # ? использовать пул соединений или передавать соединение через состояние графа (state).
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    db = SQLiteVec(
        table=table,
        connection=conn,
        embedding=embeddings,
    )

    return db.as_retriever(search_kwargs={"k": 3})


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main())
