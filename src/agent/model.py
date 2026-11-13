"""Фабрики провайдеров LLM и обработчиков эмбеддингов.
- Индексация документов в векторную БД, получение контекста из векторного поиска:
    - SQLite
- TODO Загрузка и чанкинг документов: pdf, txt, md, csv, docx, xls, xlsx.
- Инкрементальное обновление индекса при изменении папки
- Поддержка моделей через OpenAI-совместимый, GigaChat, TODO llama.cpp
"""

import hashlib
import logging
import sqlite3
from collections.abc import Iterator
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

from src.agent.config import CompletionConfig, EmbeddingConfig, Providers

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
        except Exception:
            LOGGER.info("Нет внешних данных для подключения: 'embeddings'.")
        else:
            LOGGER.info(embed_cfg.model_dump_json())
            try:
                provider = Providers(embed_cfg.provider.strip().lower())
            except Exception as e:
                LOGGER.error("Ошибка загрузки конфигурации эмбеддингов.", exc_info=e)
            embeddings = _EMBEDDING_FACTORIES[provider](embed_cfg)
            sqlite_db = SQLiteVecFactory(embed_cfg, embeddings)
            self.retrievers = sqlite_db.retrievers


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
            current_hash = self._calculate_hash(c.path)
            active_table = self._get_active_table(conn, c.path, current_hash)

            if active_table is None:
                short_hash = current_hash[:8]
                new_table = f"{c.path.name}_{short_hash}"
                LOGGER.info(f"Изменения или новая коллекция в '{c.path}' -> '{new_table}'...")

                docs = list(self._iter_docs(c.path, c.chunk_size, c.chunk_overlap))
                db = SQLiteVec.from_documents(
                    documents=docs,
                    embedding=embeddings,
                    table=new_table,
                    db_file=embed_cfg.db_path,
                )

                self._update_meta_and_cleanup(conn, c.path, current_hash, new_table)
            else:
                LOGGER.info(f"Коллекция '{c.path}' не изменилась, таблица '{active_table}'.")
                db = SQLiteVec(
                    table=active_table,
                    connection=conn,
                    embedding=embeddings,
                    db_file=embed_cfg.db_path,
                )

            dbs.append((db, c.top_k))

        self.retrievers = [db.as_retriever(search_kwargs={"k": k}) for db, k in dbs]

    def _iter_docs(self, path: Path, chunk_size: int, chunk_overlap: int) -> Iterator[Document]:
        """Загрузить чанки документов из указанной директории."""
        # ? Сам по себе Генератор/Итератор не имеет смысла, так как приводится к list для работы SQLiteVec.

        load = DirectoryLoader(
            path=path.as_uri(),
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

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    def _init_meta_table(self, db_path: str) -> None:
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

    def _calculate_hash(self, folder_path: Path) -> str:
        """Считает хеш папки на основе метаданных файлов."""
        hasher = hashlib.sha256()
        for file_path in sorted(folder_path.rglob("*")):
            if file_path.is_file():
                stat = file_path.stat()
                meta_str = f"{file_path.name}:{stat.st_size}:{stat.st_mtime}"
                hasher.update(meta_str.encode("utf-8"))
        return hasher.hexdigest()

    def _get_active_table(self, conn: sqlite3.Connection, folder: Path, current_hash: str) -> str | None:
        """Возвращает имя таблицы ТОЛЬКО если хеш совпал."""
        row: dict[str, str] = conn.execute(
            "SELECT current_hash, active_table_name FROM collection_meta WHERE collection_path = ?",
            (folder,),
        ).fetchone()

        if row and row["current_hash"] == current_hash:
            return row["active_table_name"]
        return None

    def _update_meta_and_cleanup(self, conn: sqlite3.Connection, folder: Path, hash: str, table: str) -> None:
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
                LOGGER.info("Старая таблица '%s' удалена.", old_table_name)
            except Exception as e:
                LOGGER.warning("Не удалось удалить старую таблицу '%s'", old_table_name, exc_info=e)

        conn.commit()

    # !


# ! [AI Note] Секция не_добавлять_в / удалить_из документации
class ICreateChat(Protocol):
    """Интерфейс фабрики для создания моделей чата."""

    def __call__(self, cfg: CompletionConfig) -> BaseChatModel: ...


class ICreateEmbeddings(Protocol):
    """Интерфейс фабрики для создания моделей эмбеддингов."""

    def __call__(self, cfg: EmbeddingConfig) -> Embeddings: ...


def _create_openai_compatible_chat(cfg: CompletionConfig) -> BaseChatModel:
    return ChatOpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "",
        temperature=cfg.temperature,
        max_completion_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def _create_gigachat_chat(cfg: CompletionConfig) -> BaseChatModel:
    return GigaChat(
        credentials=cfg.api_key.get_secret_value(),
        model=cfg.model or "GigaChat-2",
        verify_ssl_certs=cfg.verify_ssl_certs,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def _create_openai_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    return OpenAIEmbeddings(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "",
        dimensions=cfg.dim,
        chunk_size=cfg.batch_size,
        timeout=cfg.timeout,
    )


"""Машина состояний чата в функциональном стиле."""
_CHAT_FACTORIES: dict[Providers, ICreateChat] = {
    Providers.OPENAI: _create_openai_compatible_chat,
    Providers.GIGACHAT: _create_gigachat_chat,
}

"""Машина состояний эмбеддингов в функциональном стиле."""
_EMBEDDING_FACTORIES: dict[Providers, ICreateEmbeddings] = {
    Providers.OPENAI: _create_openai_embeddings,
}
# !
