"""Загрузка и разбиение документов для RAG."""

from collections.abc import Iterator

from langchain_community.document_loaders.directory import DirectoryLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def iter_documents(path: str) -> Iterator[Document]:
    """Загрузить документы из указанной директории."""

    load = DirectoryLoader(
        path=path,
        glob=("*.txt", "*.docx", "*.pdf", "*.md", "*.csv", "*.xls", "*.xlsx"),
        recursive=True,
        show_progress=True,
    )

    return load.lazy_load()


def iter_splits(documents: Iterator[Document], chunk_size, chunk_overlap) -> Iterator[Document]:
    """Разбить документы на чанки."""

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    for document in documents:
        yield from text_splitter.split_documents([document])
