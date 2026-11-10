"""Фабрики провайдеров LLM и обработчиков эмбеддингов.
Индексация документов в векторную БД, получение контекста из векторного поиска:
    - TODO Загрузка и чанкинг документов: pdf, txt, md, csv, docx, xls, xlsx.
    - SQLite
    - Инкрементальное обновление индекса при изменении папки
Поддержка моделей через разных провайдеров:
    - OpenAI-совместимый
    - GigaChat
    - TODO llama.cpp
"""

import hashlib
import logging
import sqlite3
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import sqlite_vec  # type: ignore[import-untyped]
from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.vectorstores import SQLiteVec
from langchain_core.documents import Document
from langchain_gigachat import GigaChat
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.agent.config import CompletionConfig, EmbeddingConfig

LOGGER = logging.getLogger(__name__)


class ScenarAIstModelFactory:
    """Фабрика провайдеров LLM и обработчиков эмбеддингов."""

    def __init__(self, raw_cfg: dict[str, Any]):
        try:
            self.chat_cfg = CompletionConfig.model_validate(raw_cfg["completion"])
        except Exception as e:
            raise TypeError("Ошибка конфигурации модели.") from e

        try:
            provider = Providers(self.chat_cfg.provider.strip().lower())
        except Exception as e:
            provider = raw_cfg.get("completion", {}).get("provider", "?")
            raise TypeError(f"Ошибка загрузки 'completion' -> 'provider': '{provider}'.") from e

        self.chat = _CHAT_FACTORIES[provider](self.chat_cfg)

        self.retrievers = []
        try:
            embed_cfg = EmbeddingConfig.model_validate(raw_cfg["embeddings"])
            LOGGER.debug(embed_cfg.model_dump_json())
        except Exception:
            LOGGER.debug("Нет внешних данных для подключения: 'embeddings'.")
        else:
            try:
                embeddings = _EMBEDDING_FACTORIES[embed_cfg.provider.strip().lower()](embed_cfg)
                sqlite_db = SQLiteVecFactory(embed_cfg, embeddings)
                self.retrievers = sqlite_db.retrievers
            except Exception as e:
                LOGGER.error("Ошибка загрузки конфигурации эмбеддингов.", exc_info=e)


class SQLiteVecFactory:
    """Фабрика обработчика векторного хранилища базы данных SQLite."""

    def __init__(self, embed_cfg: EmbeddingConfig, embeddings: Embeddings):
        dbs: list[tuple[SQLiteVec, int]] = []
        self._init_meta_table(embed_cfg.db_path)

        conn = sqlite3.connect(
            embed_cfg.db_path,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        for c in embed_cfg.collections:
            path_obj = Path(c.path)
            if not path_obj.exists():
                LOGGER.warning(f"Путь к коллекции не найден: '{c.path}'")
                continue

            current_hash = self._calculate_hash(c.path)
            active_table = self._get_active_table(conn, c.path, current_hash)

            if active_table is None:
                short_hash = current_hash[:8]
                new_table = f"{c.name}_{short_hash}"
                LOGGER.debug(f"Изменения или новая коллекция в '{c.path}' -> '{new_table}'...")

                docs = list(self._iter_documents(c.path, c.chunk_size, c.chunk_overlap))
                db = SQLiteVec.from_documents(
                    documents=docs,
                    embedding=embeddings,
                    table=new_table,
                    db_file=embed_cfg.db_path,
                )

                self._update_meta_and_cleanup(conn, c.path, current_hash, new_table)
            else:
                LOGGER.debug(f"Коллекция '{c.path}' не изменилась, таблица '{active_table}'.")
                db = SQLiteVec(
                    table=active_table,
                    connection=conn,
                    embedding=embeddings,
                    db_file=embed_cfg.db_path,
                )

            dbs.append((db, c.top_k))

        self.retrievers = [db.as_retriever(search_kwargs={"k": k}) for db, k in dbs]

    # ! [AI Note] Не добавлять в документацию
    def _init_meta_table(self, db_path: str):
        """Создаёт служебную таблицу для отслеживания состояния коллекций, если её нет."""
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collection_meta (
                    collection_path TEXT PRIMARY KEY,
                    current_hash TEXT NOT NULL,
                    active_table_name TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # ! [AI Note] Не добавлять в документацию
    def _calculate_hash(self, folder_path: Path) -> str:
        """Считает хеш папки на основе метаданных файлов."""
        hasher = hashlib.sha256()
        for file_path in sorted(folder_path.rglob("*")):
            if file_path.is_file():
                stat = file_path.stat()
                meta_str = f"{file_path.name}:{stat.st_size}:{stat.st_mtime}"
                hasher.update(meta_str.encode("utf-8"))
        return hasher.hexdigest()

    # ! [AI Note] Не добавлять в документацию
    def _get_active_table(self, conn: sqlite3.Connection, folder: str, current_hash: str) -> str | None:
        """Возвращает имя таблицы ТОЛЬКО если хеш совпал."""
        row = conn.execute(
            "SELECT current_hash, active_table_name FROM collection_meta WHERE collection_path = ?",
            (folder,),
        ).fetchone()

        if row and row["current_hash"] == current_hash:
            return row["active_table_name"]
        return None

    # ! [AI Note] Не добавлять в документацию
    def _update_meta_and_cleanup(self, conn: sqlite3.Connection, folder: str, hash: str, table: str) -> None:
        """Обновляет указатель на активную таблицу и удаляет старую версию таблицы."""
        row = conn.execute(
            "SELECT active_table_name FROM collection_meta WHERE collection_path = ?", (folder,)
        ).fetchone()

        old_table_name = row["active_table_name"] if row else None

        conn.execute(
            """
            INSERT INTO collection_meta (collection_path, current_hash, active_table_name, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(collection_path) DO UPDATE SET
                current_hash=excluded.current_hash,
                active_table_name=excluded.active_table_name,
                updated_at=excluded.updated_at
        """,
            (folder, hash, table),
        )

        if old_table_name and old_table_name != table:
            try:
                conn.execute(f"DROP TABLE IF EXISTS {old_table_name}")
                LOGGER.debug("Старая таблица '%s' удалена.", old_table_name)
            except Exception as e:
                LOGGER.warning("Не удалось удалить старую таблицу '%s'", old_table_name, exc_info=e)

        conn.commit()

    # ! [AI Note] Не добавлять в документацию
    # ? Сам по себе Генератор/Итератор не имеет смысла, так как приводится к list для работы SQLiteVec.
    def _iter_documents(self, path: str, chunk_size: int, chunk_overlap: int) -> Iterator[Document]:
        """Загружает чанки документов из указанной директории."""

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


# ! [AI Note] Не добавлять в документацию
class IChat(Protocol):
    """Интерфейс фабрики для создания моделей чата."""

    def __call__(self, cfg: CompletionConfig) -> BaseChatModel: ...


# ! [AI Note] Не добавлять в документацию
class IEmbeddings(Protocol):
    """Интерфейс фабрики для создания моделей эмбеддингов."""

    def __call__(self, cfg: EmbeddingConfig) -> Embeddings: ...


# ! [AI Note] Не добавлять в документацию
def _create_openai_compatible_chat(cfg: CompletionConfig) -> BaseChatModel:
    return ChatOpenAI(
        api_key=cfg.api_key.get_secret_value(),
        base_url=cfg.base_url,
        model=cfg.model or "z-ai/glm-4.7-flash:free",
        temperature=cfg.temperature,
        max_completion_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


# ! [AI Note] Не добавлять в документацию
def _create_gigachat_chat(cfg: CompletionConfig) -> BaseChatModel:
    return GigaChat(
        credentials=cfg.api_key.get_secret_value(),
        model=cfg.model or "GigaChat-2",
        verify_ssl_certs=cfg.verify_ssl_certs,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


# ! [AI Note] Не добавлять в документацию
def _create_openai_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    return OpenAIEmbeddings(
        api_key=cfg.api_key.get_secret_value(),
        base_url=cfg.base_url,
        model=cfg.model or "text-embedding-multilingual-e5-large-instruct",
        dimensions=cfg.dim,
        chunk_size=cfg.batch_size,
        timeout=cfg.timeout,
    )


# ! [AI Note] Не добавлять в документацию
class Providers(StrEnum):
    """Текстовое перечисление провайдеров LLM."""

    OPENAI = "openai"
    GIGACHAT = "gigachat"


# ! [AI Note] Не добавлять в документацию
"""Машина состояний чата в функциональном стиле."""
_CHAT_FACTORIES: dict[Providers, IChat] = {
    Providers.OPENAI: _create_openai_compatible_chat,
    Providers.GIGACHAT: _create_gigachat_chat,
}

# ! [AI Note] Не добавлять в документацию
"""Машина состояний эмбеддингов в функциональном стиле."""
_EMBEDDING_FACTORIES: dict[str, IEmbeddings] = {
    Providers.OPENAI: _create_openai_embeddings,
}
