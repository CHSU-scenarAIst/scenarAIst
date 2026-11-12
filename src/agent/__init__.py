"""Пакет 'Обработка эмбеддингов'."""

from importlib.metadata import version

__version__ = version("scenaraist")

# # Create prompt template
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
