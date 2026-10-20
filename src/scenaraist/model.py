"""
Фабрики провайдеров LLM и эмбеддингов.
Ретриверы для RAG-поиска по документам, загруженным в векторную БД SQLite.
"""

import logging
import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Protocol

import sqlite_vec
from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.vectorstores import SQLiteVec
from langchain_gigachat import GigaChat
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.memory import InMemorySaver

# from langchain_tavily import TavilySearch
from scenaraist.config import CompletionConfig, EmbeddingConfig

LOGGER = logging.getLogger(__name__)


# TODO привести к объектному подходу
def get_model(cfg):
    try:
        chat_cfg = CompletionConfig.model_validate(cfg["completion"])
        chat = CHAT_FACTORIES[chat_cfg.provider.strip().lower()](chat_cfg)
    except Exception:
        LOGGER.exception("Ошибка загрузки конфигурации модели")
        raise

    retriever = []
    try:
        embed_cfg = EmbeddingConfig.model_validate(cfg["embeddings"])
        try:
            embed = EMBEDDING_FACTORIES[embed_cfg.provider.strip().lower()](embed_cfg)
            retriever = SQLiteVecRetriever().from_config(embed_cfg, embed)
        except Exception:
            LOGGER.exception("Ошибка загрузки конфигурации эмбеддингов")
    except Exception:
        LOGGER.warning("Нет внешних данных для подключения")

    # ? на будущее: SQLite/Postgres Checkpointer
    checkpointer = InMemorySaver()

    # ! Инструменты агента (бесполезно)
    tools = []
    try:
        ...
    #     tavily = TavilyConfig(cfg)
    #     web_search = TavilySearch(tavily_api_key=tavily.api_key, max_results=tavily.top_k, topic="general")
    #     tools = [web_search]
    except Exception:
        LOGGER.exception("Ошибка при передаче инструментов")

    return chat, chat_cfg.system_prompt, chat_cfg.max_steps, checkpointer, retriever, tools


class SQLiteVecRetriever:
    """Фабрика ретриверов поверх векторного хранилища SQLiteVec."""

    def from_config(
        self,
        embed_cfg: EmbeddingConfig,
        embeddings: Embeddings,
    ):
        """Создать ретриверы для всех коллекций из конфигурации эмбеддингов."""

        dbs: list[tuple[SQLiteVec, int]] = []
        db_path_exists = Path(embed_cfg.db_path).exists()

        for c in embed_cfg.collections:
            if not db_path_exists:
                docs = list(
                    self.__iter_documents(
                        c.path,
                        c.chunk_size,
                        c.chunk_overlap,
                    )
                )
                db = SQLiteVec.from_documents(
                    documents=docs,
                    embedding=embeddings,
                    table=c.name,
                    db_file=embed_cfg.db_path,
                )
            else:
                conn = sqlite3.connect(
                    embed_cfg.db_path,
                    check_same_thread=False,
                )
                conn.row_factory = sqlite3.Row
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)

                db = SQLiteVec(
                    table=c.name,
                    connection=conn,
                    embedding=embeddings,
                    db_file=embed_cfg.db_path,
                )

            dbs.append((db, c.top_k))

        return [db.as_retriever(search_kwargs={"k": k}) for db, k in dbs]

    def __iter_documents(
        self,
        path: str,
        chunk_size: int,
        chunk_overlap: int,
    ):
        """Загрузить чанки документов из указанной директории."""

        load = DirectoryLoader(
            path=path,
            glob=("*.txt", "*.docx", "*.pdf", "*.md", "*.csv", "*.xls", "*.xlsx"),
            recursive=True,
            show_progress=True,
        )
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        docs = load.lazy_load()
        for d in docs:
            yield from text_splitter.split_documents([d])


# ! Не включать в документацию


def __create_openai_compatible_chat(cfg: CompletionConfig) -> BaseChatModel:
    return ChatOpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "z-ai/glm-4.7-flash:free",
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def __create_gigachat_chat(cfg: CompletionConfig) -> BaseChatModel:
    return GigaChat(
        credentials=cfg.api_key,
        model=cfg.model or "GigaChat-2",
        verify_ssl_certs=cfg.verify_ssl_certs,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def __create_openai_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    return OpenAIEmbeddings(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "text-embedding-multilingual-e5-large-instruct",
        dimensions=cfg.dim,
        chunk_size=cfg.batch_size,
        timeout=cfg.timeout,
    )


class Providers(StrEnum):
    OPENAI = "openai"
    GIGACHAT = "gigachat"


class IChat(Protocol):
    """Интерфейс фабрики для создания моделей чата."""

    def __call__(self, cfg: CompletionConfig) -> BaseChatModel: ...


class IEmbeddings(Protocol):
    """Интерфейс фабрики для создания моделей эмбеддингов."""

    def __call__(self, cfg: EmbeddingConfig) -> Embeddings: ...


CHAT_FACTORIES: dict[Providers, IChat] = {
    Providers.OPENAI: __create_openai_compatible_chat,
    Providers.GIGACHAT: __create_gigachat_chat,
}

EMBEDDING_FACTORIES: dict[str, IEmbeddings] = {
    Providers.OPENAI: __create_openai_embeddings,
}
