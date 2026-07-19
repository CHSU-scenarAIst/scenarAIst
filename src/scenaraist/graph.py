"""Сборка и компиляция графа LangGraph."""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langchain.chat_models import BaseChatModel
from langchain.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, add_messages
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import ValidationError

from .tools import MATH_TOOLS, JsonResponse, format_response, web_search

LOGGER = logging.getLogger(__name__)


class OrchestratorState(TypedDict):
    """Состояние графа оркестратора."""

    messages: Annotated[list[AnyMessage], add_messages]
    # TODO Нет механизма принудительного завершения после N вызовов.
    llm_calls: int
    # db_path: str  # Путь к SQLite базе
    # urls: list[str]  # Найденные ссылки
    # topic: str  # Тема исследования
    # csv_path: str  # Путь к CSV файлу
    # report_path: str  # Путь к итоговому отчёту


def build_agent(llm: BaseChatModel) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Собрать и скомпилировать граф состояний агента."""

    web_tool = web_search().as_tool()
    all_tools = [*MATH_TOOLS, format_response, web_tool]
    llm_with_tools = llm.bind_tools(all_tools)

    def chat(state: OrchestratorState) -> OrchestratorState:
        """Узел вызова LLM с текущей историей сообщений."""

        LOGGER.debug("Вызов чатбота с %d сообщениями", len(state["messages"]))
        prompt = [
            SystemMessage(
                content=(
                    "You are a helpful assistant. Отвечай на языке поступившего запроса.\n"
                    "Используй инструменты, когда они необходимы для получения ответа.\n"
                    "Use web search to find accurate, up-to-date information.\n"
                    f"Today's date is {datetime.now(UTC):%B %d, %Y}."
                )
            ),
            *state["messages"],
        ]
        return {
            "messages": [llm_with_tools.invoke(prompt)],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

    # TODO Математические инструменты сгруппированы в один ToolNode, а веб-поиск — в отдельный.
    # Это архитектурное решение вынуждает роутер выбирать только один путь, и если
    # модель вызывает add и web_search одновременно, второй вызов будет проигнорирован.
    math_tool_node = ToolNode(MATH_TOOLS)
    web_tool_node = ToolNode([web_tool])
    builder = StateGraph(OrchestratorState)

    # Узлы графа
    builder.add_node(chat.__name__, chat)
    builder.add_node(ToolName.MATH, math_tool_node)
    builder.add_node(ToolName.WEB, web_tool_node)
    builder.add_node(ToolName.FINAL, final)

    # Структура графа
    builder.add_edge(START, chat.__name__)
    builder.add_edge(ToolName.MATH, chat.__name__)
    builder.add_edge(ToolName.WEB, chat.__name__)
    builder.add_conditional_edges(
        chat.__name__,
        router,
        {
            ToolName.MATH: ToolName.MATH,
            ToolName.FINAL: ToolName.FINAL,
            ToolName.WEB: ToolName.WEB,
        },
    )
    builder.add_edge(ToolName.FINAL, END)

    # Сборка агента
    # checkpointer = InMemorySaver()
    agent = builder.compile()
    # display(Image(graph.get_graph().draw_mermaid_png()))
    LOGGER.info("Граф скомпилирован")
    return agent


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
        return ToolName.FINAL

    # TODO Роутер проверяет только tool_calls[0]["name"], игнорируя
    # все остальные вызовы инструментов, если LLM решит вызвать несколько инструментов одновременно.
    # Это приводит к потере вызовов инструментов,
    # если модель решает вызвать, например, add и web_search в одном ответе.
    tool_name = tool_calls[0]["name"]

    if tool_name in MATH_TOOL_NAMES:
        return ToolName.MATH

    if tool_name == format_response.name:
        return ToolName.FINAL

    # TODO - зафиксировать имя tavily_search
    if str(tool_name).endswith("tavily_search"):
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
        except ValidationError as e:
            LOGGER.warning("Некорректный JSON от модели: %s", e)
            response = JsonResponse(
                status="error",
                message="Модель сформировала некорректный ответ.",
                data={"validation_error": e.errors()},
            )
        return {
            "messages": [
                ToolMessage(content="OK", tool_call_id=call["id"], name=format_response.name),
                AIMessage(content=response.model_dump_json(indent=2)),
            ],
        }

    content = getattr(last, "content", "")
    fallback = JsonResponse(status="OK", message=str(content), data={})

    return {"messages": [AIMessage(content=fallback.model_dump_json(indent=2))]}
