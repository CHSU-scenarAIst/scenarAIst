"""Пакет 'Обработка эмбеддингов'."""

from importlib.metadata import version

__version__ = version("scenaraist")

# ? Create prompt template
# prompt = ChatPromptTemplate.from_messages([
#     ("system", "You are a professional {domain} expert"),
#     ("human", "Please explain the concept and applications of {topic}")
# ])

# # Create chain
# chain = prompt | llm

# # Invoke chain
# response = chain.invoke({
#     "domain": "machine learning",
#     "topic": "deep learning"
# })

# print(response.content)

# ? InMemorySaver/SQLite/Postgres Checkpointer
# from langgraph.checkpoint.memory import InMemorySaver()
# self._checkpointer = InMemorySaver
# self.agent = builder.compile(checkpointer=self._checkpointer)
# ...
# import uuid
# from langchain_core.runnables import RunnableConfig
# run_cfg: RunnableConfig = {"configurable": {"thread_id": uuid.uuid4().hex}}
# response = self.agent.invoke(input=state, config=run_cfg)

# ? Qdrant (langchain-qdrant). Поддерживает локальный файловый режим (QdrantClient(path="./qdrant_db"))
# и имеет активно поддерживаемую интеграцию.
