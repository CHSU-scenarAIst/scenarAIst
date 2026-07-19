import logging
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path

from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyMuPDFLoader,
    TextLoader,
    UnstructuredExcelLoader,
)
from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

LOADERS: dict[str, Callable[[str], BaseLoader]] = {
    ".pdf": PyMuPDFLoader,
    ".docx": Docx2txtLoader,
    ".txt": partial(TextLoader, autodetect_encoding=True),
    ".md": partial(TextLoader, autodetect_encoding=True),
    ".csv": partial(TextLoader, autodetect_encoding=True),
    ".xls": UnstructuredExcelLoader,
    ".xlsx": UnstructuredExcelLoader,
}
LOGGER = logging.getLogger(__name__)


def iter_documents(folder: str | Path) -> Iterator[Document]:
    """TODO"""

    root = Path(folder)
    for file in root.rglob("*"):
        loader_cls = LOADERS.get(file.suffix.lower())
        if loader_cls is None:
            continue

        loader = loader_cls(str(file))
        try:
            yield from loader.lazy_load()
        except Exception as e:
            LOGGER.warning("Не удалось обработать %s: %s", file, e)


def iter_splits(documents: Iterator[Document]) -> Iterator[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, length_function=len
    )
    for document in documents:
        yield from text_splitter.split_documents([document])


# from langchain_chroma import Chroma

# collection_name = "my_collection"
# vectorstore = Chroma.from_documents(
#     collection_name=collection_name,
#     documents=splits,
#     embedding=embedding_function,
#     persist_directory="./chroma_db",
# )


# from langchain.tools import tool
# from pydantic import BaseModel


# class RagToolSchema(BaseModel):
#     question: str


# @tool(args_schema=RagToolSchema)
# def retriever_tool(question):
#     """
#     Tool to Retrieve Semantically Similar documents
#     to answer User Questions related to FutureSmart AI
#     """
#     print("INSIDE RETRIEVER NODE")
#     retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
#     retriever_result = retriever.invoke(question)
#     return "\n\n".join(doc.page_content for doc in retriever_result)


# retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
# # pass question
# retriever_results = retriever.invoke("Who is the founder of Futuresmart AI?")
# print(retriever_results)
