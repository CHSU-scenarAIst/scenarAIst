"""Фабрики провайдеров LLM и обработчиков эмбеддингов."""

import logging
import sqlite3
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import sqlite_vec  # type: ignore[import-untyped]
from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.vectorstores import SQLiteVec
from langchain_core.documents import Document
from langchain_gigachat import GigaChat
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import SecretStr

from src.agent.config import CompletionConfig, EmbeddingConfig

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

# from langgraph.checkpoint.memory import InMemorySaver
# from langchain_tavily import TavilySearch

LOGGER = logging.getLogger(__name__)


class ScenarAIstModelFactory:
    def __init__(self, cfg: dict[str, Any]) -> None:
        try:
            chat_cfg = CompletionConfig.model_validate(cfg["completion"])
            try:
                provider = _Providers(chat_cfg.provider.strip().lower())
                self.chat = _CHAT_FACTORIES[provider](chat_cfg)
                self.system_prompt = chat_cfg.system_prompt
                self.max_steps = chat_cfg.max_steps
            except Exception as err:
                provider = cfg.get("completion", {}).get("provider", "?")
                raise TypeError(f"Ошибка загрузки конфигурации модели: провайдер '{provider}'") from err
        except Exception as err:
            raise TypeError("Ошибка конфигурации модели") from err

        self.retrievers = []
        try:
            embed_cfg = EmbeddingConfig.model_validate(cfg["embeddings"])
            try:
                embed = _EMBEDDING_FACTORIES[embed_cfg.provider.strip().lower()](embed_cfg)
                sqlite_db = SQLiteVecFactory(embed_cfg, embed)
                self.retrievers = sqlite_db.retrievers
            except Exception as e:
                LOGGER.error("Ошибка загрузки конфигурации эмбеддингов", exc_info=e)
        except Exception as e:
            LOGGER.debug("Нет внешних данных для подключения", exc_info=e)

        # ? SQLite/Postgres Checkpointer
        # self.checkpointer = InMemorySaver()
        self.checkpointer = None

        # ? Инструменты агента (бесполезно)
        self.tools: list[BaseTool] = []
        try:
            ...
        #     tavily = TavilyConfig(cfg)
        #     web_search = TavilySearch(
        #         tavily_api_key=tavily.api_key,
        #         max_results=tavily.top_k,
        #         topic="general",
        #     )
        #     tools = [web_search]
        except Exception as e:
            LOGGER.error("Ошибка при создании инструментов", exc_info=e)


class SQLiteVecFactory:
    """Фабрика обработчиков эмбеддингов и векторного хранилища БД SQLite."""

    def __init__(
        self,
        embed_cfg: EmbeddingConfig,
        embeddings: Embeddings,
    ):
        dbs: list[tuple[SQLiteVec, int]] = []
        db_path_exists = Path(embed_cfg.db_path).exists()

        for c in embed_cfg.collections:
            if not db_path_exists:
                docs = list(
                    _iter_documents(
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

        self.retrievers = [db.as_retriever(search_kwargs={"k": k}) for db, k in dbs]


def _iter_documents(
    path: str,
    chunk_size: int,
    chunk_overlap: int,
) -> Iterator[Document]:
    """
    Загружает чанки документов из указанной директории.
    Сам по себе Генератор/Итератор не имеет смысла, так как приводится к list для работы SQLiteVec.
    ! [AI Note] Не добавлять в документацию
    """

    load = DirectoryLoader(
        path=path,
        glob=["*.txt", "*.docx", "*.pdf", "*.md", "*.csv", "*.xls", "*.xlsx"],
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


class _Providers(StrEnum):
    """
    Текстовое перечисление провайдеров.
    ! [AI Note] Не добавлять в документацию
    """

    OPENAI = "openai"
    GIGACHAT = "gigachat"


class _IChat(Protocol):
    """
    Интерфейс фабрики для создания моделей чата.
    ! [AI Note] Не добавлять в документацию
    """

    def __call__(self, cfg: CompletionConfig) -> BaseChatModel: ...


class _IEmbeddings(Protocol):
    """
    Интерфейс фабрики для создания моделей эмбеддингов.
    ! [AI Note] Не добавлять в документацию
    """

    def __call__(self, cfg: EmbeddingConfig) -> Embeddings: ...


def _create_openai_compatible_chat(cfg: CompletionConfig) -> BaseChatModel:
    """
    ! [AI Note] Не добавлять в документацию
    """
    return ChatOpenAI(
        api_key=SecretStr(cfg.api_key),
        base_url=cfg.base_url,
        model=cfg.model or "z-ai/glm-4.7-flash:free",
        temperature=cfg.temperature,
        max_completion_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def _create_gigachat_chat(cfg: CompletionConfig) -> BaseChatModel:
    """
    ! [AI Note] Не добавлять в документацию
    """
    return GigaChat(
        credentials=cfg.api_key,
        model=cfg.model or "GigaChat-2",
        verify_ssl_certs=cfg.verify_ssl_certs,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def _create_openai_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    """
    ! [AI Note] Не добавлять в документацию
    """
    return OpenAIEmbeddings(
        api_key=SecretStr(cfg.api_key),
        base_url=cfg.base_url,
        model=cfg.model or "text-embedding-multilingual-e5-large-instruct",
        dimensions=cfg.dim,
        chunk_size=cfg.batch_size,
        timeout=cfg.timeout,
    )


"""
Машина состояний чата в функциональном стиле.
! [AI Note] Не добавлять в документацию
"""
_CHAT_FACTORIES: dict[_Providers, _IChat] = {
    _Providers.OPENAI: _create_openai_compatible_chat,
    _Providers.GIGACHAT: _create_gigachat_chat,
}

"""
Машина состояний эмбеддингов в функциональном стиле.
! [AI Note] Не добавлять в документацию
"""
_EMBEDDING_FACTORIES: dict[str, _IEmbeddings] = {
    _Providers.OPENAI: _create_openai_embeddings,
}
