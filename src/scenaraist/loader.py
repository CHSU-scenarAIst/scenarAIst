import os

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_core.documents import Document

# from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_documents(folder_path: str) -> list[Document]:
    documents = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        elif filename.endswith(".docx"):
            loader = Docx2txtLoader(file_path)
        else:
            print(f"Unsupported file type: {filename}")
            continue
        documents.extend(loader.load())
    return documents


folder_path = "/content/docs"
documents = load_documents(folder_path)
print(f"Loaded {len(documents)} documents from the folder.")

# text_splitter = RecursiveCharacterTextSplitter(
#     chunk_size=1000, chunk_overlap=200, length_function=len
# )

# splits = text_splitter.split_documents(documents)
# print(f"Split the documents into {len(splits)} chunks.")

# from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings

# embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

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
