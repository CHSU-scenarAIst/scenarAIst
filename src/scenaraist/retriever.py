"""Ретриверы для RAG-поиска по документам, загруженным в векторную БД SQLite."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import sqlite_vec
from langchain.embeddings import Embeddings
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.vectorstores import SQLiteVec
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter

from scenaraist.config import EmbeddingConfig


class SQLiteVecRetriever:
    """Фабрика ретриверов поверх векторного хранилища SQLiteVec."""

    def from_config(self, embed_cfg: EmbeddingConfig, embeddings: Embeddings) -> list[BaseRetriever]:
        """Создать ретриверы для всех коллекций из конфигурации эмбеддингов."""

        dbs: list[tuple[SQLiteVec, int]] = []
        db_path_exists = Path(embed_cfg.db_path).exists()

        for c in embed_cfg.collections:
            if not db_path_exists:
                docs = list(self.__iter_documents(c.path, c.chunk_size, c.chunk_overlap))
                db = SQLiteVec.from_documents(
                    documents=docs,
                    embedding=embeddings,
                    table=c.name,
                    db_file=embed_cfg.db_path,
                )
            else:
                conn = sqlite3.connect(embed_cfg.db_path, check_same_thread=False)
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

    def __iter_documents(self, path: str, chunk_size: int, chunk_overlap: int) -> Iterator[Document]:
        """Загрузить чанки документов из указанной директории."""

        load = DirectoryLoader(
            path=path,
            glob=("*.txt", "*.docx", "*.pdf", "*.md", "*.csv", "*.xls", "*.xlsx"),
            recursive=True,
            show_progress=True,
        )

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        docs = load.lazy_load()
        for d in docs:
            yield from text_splitter.split_documents([d])
