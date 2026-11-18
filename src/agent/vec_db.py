"""Сборщики обработчиков эмбеддингов разных провайдеров.
- Загрузка и чанкинг документов: pdf, txt, md, csv, docx, xls, xlsx.
- Инкрементальное обновление индекса при изменении папки
- Поддержка моделей через OpenAI-совместимый (в т.ч. llama.cpp-сервер), GigaChat
- Индексация документов в векторную БД, получение контекста из векторного поиска.
    - SQLite
"""

import hashlib
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import sqlite_vec  # type: ignore[import-untyped]
from langchain.embeddings import Embeddings
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.vectorstores import SQLiteVec
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


class CollectionConfig(BaseModel):
    """Конфигурация одной коллекции документов для векторного поиска."""

    path: Path = Field(description="Путь к папке с документами коллекции.")

    top_k: int = Field(default=5, ge=1, description="Сколько наиболее близких чанков возвращать.")
    chunk_size: int = Field(default=512, ge=1, description="Размер чанка (в символах).")
    chunk_overlap: int = Field(default=64, ge=0, description="Перекрытие чанков для сохранения контекста.")


class VectoreStoreBuilder:
    """Сборщик обработчика векторного хранилища."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collection_meta (
                    collection_path TEXT PRIMARY KEY,
                    current_hash TEXT NOT NULL,
                    active_table_name TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def build(self, embeddings: Embeddings, collections: list[CollectionConfig]) -> None:
        self.embeddings = embeddings
        self.conn = sqlite3.connect(database=self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)

        dbs: list[tuple[SQLiteVec, int]] = []
        for c in collections:
            current_hash = self._calculate_hash(c.path)
            sqlite_db = self._get_vector_db(c.path, current_hash, c.chunk_size, c.chunk_overlap)
            dbs.append((sqlite_db, c.top_k))

        self.retrivers = [db.as_retriever(search_kwargs={"k": k}) for db, k in dbs]

    def _iter_docs(self, path: Path, chunk_size: int, chunk_overlap: int) -> Iterator[Document]:
        """Загрузить документы из указанной директории."""
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
    def _calculate_hash(self, folder_path: Path) -> str:
        """Считает хеш папки на основе метаданных файлов."""
        hasher = hashlib.sha256()
        for file_path in sorted(folder_path.rglob("*")):
            if file_path.is_file():
                stat = file_path.stat()
                meta_str = f"{file_path.name}:{stat.st_size}:{stat.st_mtime}"
                hasher.update(meta_str.encode("utf-8"))
        return hasher.hexdigest()

    def _get_vector_db(self, folder: Path, hash: str, size: int, overlap: int) -> SQLiteVec:
        """Возвращает имя таблицы ТОЛЬКО если хеш совпал."""
        row: dict[str, str] = self.conn.execute(
            "SELECT current_hash, active_table_name FROM collection_meta WHERE collection_path = ?",
            (folder,),
        ).fetchone()

        if row and row["current_hash"] == hash:
            active_table = row["active_table_name"]
            LOGGER.info(f"Коллекция '{folder}' не изменилась, таблица '{active_table}'.")
            return SQLiteVec(
                table=active_table,
                connection=self.conn,
                embedding=self.embeddings,
                db_file=self.db_path,
            )

        short_hash = hash[:8]
        new_table = f"{folder.name}_{short_hash}"
        LOGGER.info(f"Изменения или новая коллекция в '{folder}' -> '{new_table}'...")

        docs = list(self._iter_docs(folder, size, overlap))
        sqlite_db = SQLiteVec.from_documents(
            documents=docs,
            embedding=self.embeddings,
            table=new_table,
            db_file=self.db_path,
        )
        self._update_meta_and_cleanup(folder, hash, new_table)
        return sqlite_db

    def _update_meta_and_cleanup(self, folder: Path, hash: str, table: str) -> None:
        """Обновляет указатель на активную таблицу и удаляет старую версию таблицы."""
        row = self.conn.execute(
            "SELECT active_table_name FROM collection_meta WHERE collection_path = ?", (folder,)
        ).fetchone()

        old_table_name = row["active_table_name"] if row else None

        self.conn.execute(
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
                self.conn.execute(f"DROP TABLE IF EXISTS {old_table_name}")
                LOGGER.info("Старая таблица '%s' удалена.", old_table_name)
            except Exception as e:
                LOGGER.warning("Не удалось удалить старую таблицу '%s'", old_table_name, exc_info=e)

        self.conn.commit()
