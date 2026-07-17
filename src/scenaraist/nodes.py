"""Узлы графа агента — ветвление и финальное форматирование."""

import logging
from enum import StrEnum

from langchain.messages import AIMessage, ToolMessage
from pydantic import ValidationError

from .state import OrchestratorState
from .tools import MATH_TOOLS, JsonResponse, format_response

LOGGER = logging.getLogger(__name__)
MATH_TOOL_NAMES = {tool.name for tool in MATH_TOOLS}


class ToolName(StrEnum):
    """Имена узлов графа с инструментами."""

    MATH = "math_tools"
    WEB = "web_tool"
    FINAL = "final_tool"


def router(state: OrchestratorState) -> ToolName:
    """Ветвление между узлами графа."""

    LOGGER.info("Ветвление: %s", router.__name__)

    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", [])

    if not tool_calls:
        LOGGER.info("Модель не вызвала инструменты")
        return ToolName.FINAL

    tool_name = tool_calls[0]["name"]

    if tool_name in MATH_TOOL_NAMES:
        LOGGER.info("Модель вызвала: %s", tool_name)
        return ToolName.MATH

    if tool_name == format_response.name:
        LOGGER.info("Модель вызвала: %s", tool_name)
        return ToolName.FINAL

    # TODO - зафиксировать имя tavily_search
    if str(tool_name).endswith("search"):
        LOGGER.info("Модель вызвала: %s", tool_name)
        return ToolName.WEB

    LOGGER.warning("Неизвестный инструмент: %s", tool_name)
    return ToolName.FINAL


def final(state: OrchestratorState) -> OrchestratorState:
    """Узел гарантированного форматирования ответа."""

    LOGGER.info("Форматирование: %s", final.__name__)

    last = state["messages"][-1]
    tool_calls = getattr(last, "tool_calls", [])
    call = tool_calls[0] if tool_calls else None

    if call and call["name"] == format_response.name:
        try:
            response = JsonResponse(**call["args"])
            LOGGER.info("Ответ успешно сформирован")
        except ValidationError as e:
            LOGGER.warning("Некорректный JSON от модели: %s", e)
            response = JsonResponse(
                status="error",
                message="Модель сформировала некорректный ответ.",
                data={"validation_error": e.errors()},
            )
        return {
            "messages": [
                ToolMessage(
                    content="OK",
                    tool_call_id=call["id"],
                    name=format_response.name,
                ),
                AIMessage(content=response.model_dump_json(indent=2)),
            ],
        }

    content = getattr(last, "content", "")
    fallback = JsonResponse(
        status="OK",
        message=str(content),
        data={},
    )

    return {"messages": [AIMessage(content=fallback.model_dump_json(indent=2))]}
