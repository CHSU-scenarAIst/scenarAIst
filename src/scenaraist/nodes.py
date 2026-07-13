"""Узлы графа агента — ветвление и финальное форматирование."""

import logging

from langchain.messages import AIMessage, ToolMessage

from .state import OrchestratorState, ToolName
from .tools import MATH_TOOLS, JsonResponse, format_response

LOGGER = logging.getLogger(__name__)
MATH_TOOLS_NAMES = [tool.name for tool in MATH_TOOLS]


def router(state: OrchestratorState) -> ToolName:
    """Ветвление между узлами графа."""

    last = state["messages"][-1]

    tool_calls = getattr(last, "tool_calls", [])

    if tool_calls and tool_calls[0]["name"] in MATH_TOOLS_NAMES:
        LOGGER.debug(f"Модель вызвала: {last.tool_calls[0]['name']}")
        return ToolName.MATH

    return ToolName.FINAL


def final(state: OrchestratorState) -> OrchestratorState:
    """Узел гарантированного форматирования ответа."""
    LOGGER.info("Форматирование финального ответа в JSON")

    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", [])

    if tool_calls and tool_calls[0]["name"] == format_response.name:
        call = tool_calls[0]
        return {
            "messages": [
                ToolMessage(
                    content="JSON сформирован успешно",
                    tool_call_id=call["id"],
                    name=format_response.name,
                ),
                AIMessage(content=JsonResponse(**call["args"]).model_dump_json(indent=2)),
            ]
        }

    fallback = JsonResponse(status="success", message=str(last.content or ""), data={})
    return {"messages": [AIMessage(content=fallback.model_dump_json(indent=2))]}
