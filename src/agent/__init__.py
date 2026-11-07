"""Пакет "Обработка эмбеддингов". Сборка LLM-агента с инструментами и обработчиками эмбеддингов документов."""

from importlib.metadata import version

__version__ = version("scenaraist")

# # ? NOTTODO data={...}
# response = JsonResponse(
#     query=state["query"],
#     message=message,
#     data={},
#     actions=[],
#     add_instruct=state["add_instruct"],
# )

# HumanMessage(f"Систематизируй, отформатируй и упакуй итоговый ответ:\n\n{raw_response}")
# *messages,
