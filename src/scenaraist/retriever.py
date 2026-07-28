from collections.abc import Iterator
from pathlib import Path

from langchain.embeddings import Embeddings
from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_community.vectorstores import SQLiteVec
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter

from scenaraist.config import EmbeddingConfig


class StorageRetriever:
    def from_config(self, embed_cfg: EmbeddingConfig, embeddings: Embeddings) -> list[BaseRetriever]:
        dbs: list[tuple[SQLiteVec, int]] = []

        if not Path(embed_cfg.db_path).exists():
            for c in embed_cfg.collections:
                docs = self.__iter_documents(c.path, c.chunk_size, c.chunk_overlap)
                dbs.append(
                    (
                        SQLiteVec.from_documents(
                            documents=docs,
                            embedding=embeddings,
                            table=c.name,
                            db_file=embed_cfg.db_path,
                        ),
                        c.top_k,
                    )
                )

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
