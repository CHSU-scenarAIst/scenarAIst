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


class StorageRetriever:
    def __init__(
        self,
        folder_path: str,
        db_path: str,
        table: str,
        embeddings: Embeddings,
        chunk_size: int,
        chunk_overlap: int,
    ):
        self.embeddings = embeddings
        self.db_path = db_path
        self.table = table

        if not Path(db_path).exists():
            documents = self.__iter_documents(folder_path, chunk_size, chunk_overlap)
            SQLiteVec.from_documents(
                documents=documents,
                embedding=embeddings,
                table=table,
                db_file=db_path,
            )

    def get_storage_retriever(self, k: int = 3) -> BaseRetriever:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        db = SQLiteVec(
            table=self.table,
            connection=conn,
            embedding=self.embeddings,
        )

        return db.as_retriever(search_kwargs={"k": k})

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
