"""
Пакет "Обработка эмбеддингов"
Сборка LLM-агента с инструментами и обработчиками эмбеддингов документов.
"""

from importlib.metadata import version

__version__ = version("scenaraist")


import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from langchain.messages import HumanMessage, SystemMessage
from langchain_core.documents import Document
from langgraph.graph import END, START, MessagesState
from langgraph.graph.state import StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from src.agent.model import ScenarAIstModelFactory

LOGGER = logging.getLogger(__name__)


class ScenarAIstAgent:
    """Сборщик агента-Сценариста с инструментами и источниками знаний."""

    # ? with_structured_output()
    def __init__(self, raw_cfg):
        """Сборка LLM-агента."""

        cfg = ScenarAIstModelFactory(raw_cfg)
        agent_llm = cfg.chat.bind_tools(cfg.tools)

        def _retrieve_node(state: _OrchestratorState):
            """
            Узел поиска релевантных документов по запросу.
            ! [AI Note] Не добавлять в документацию
            """

            if not cfg.retrievers:
                return {
                    "query": "",
                    "documents": [],
                    "steps": state.get("steps", 0) + 1,
                }

            query = _extract_query(state["messages"])
            docs = [doc for r in cfg.retrievers for doc in r.invoke(query)]

            return {
                "query": query,
                "documents": docs,
                "steps": state.get("steps", 0) + 1,
            }

        def _chat_node(state: _OrchestratorState):
            """
            Узел вызова LLM с текущей историей сообщений.
            ! [AI Note] Не добавлять в документацию
            """
            messages = state["messages"]
            docs = state.get("documents", None)
            system_content = cfg.system_prompt + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"

            if context := _prepare_context_documents(docs):
                system_content += f"<context>{context}</context>"

            response = agent_llm.invoke([SystemMessage(system_content), *messages])

            return {
                "messages": [response],
                "steps": state.get("steps", 0) + 1,
            }

        def _router_node(state: _OrchestratorState):
            """
            Ветвление после вызова LLM: исполнение инструментов либо финализация ответа.
            ! [AI Note] Не добавлять в документацию
            """

            last = state["messages"][-1]
            tool_calls = getattr(last, "tool_calls", [])

            if tool_calls and cfg.tools and state.get("steps", 0) < cfg.max_steps:
                return _NodeEnum.TOOLS

            return _NodeEnum.FORMAT

        tool_node = ToolNode(cfg.tools)

        def _tools_node(state: _OrchestratorState):
            """
            Узел исполнения инструментов, выбранных LLM.
            ! [AI Note] Не добавлять в документацию
            """

            result = tool_node.invoke(state)
            return {
                **result,
                "steps": state.get("steps", 0) + 1,
            }

        def _format_node(state: _OrchestratorState):
            """
            Узел финализации ответа в JSON-структуру.
            ! [AI Note] Не добавлять в документацию
            """

            last = state["messages"][-1]
            message = last.content

            response = JsonResponse(
                status="OK",
                message=message,
                data={},
                words=[WordItem(word=word) for word in message.split()],
            )

            return {
                "response": response,
                "steps": state.get("steps", 0) + 1,
            }

        builder = StateGraph(_OrchestratorState)

        builder.add_node(_NodeEnum.CHAT, _chat_node)
        builder.add_node(_NodeEnum.FORMAT, _format_node)

        if cfg.retrievers:
            builder.add_node(_NodeEnum.RETRIEVE, _retrieve_node)
            builder.add_edge(START, _NodeEnum.RETRIEVE)
            builder.add_edge(_NodeEnum.RETRIEVE, _NodeEnum.CHAT)
        else:
            builder.add_edge(START, _NodeEnum.CHAT)

        if cfg.tools:
            builder.add_node(_NodeEnum.TOOLS, _tools_node)
            conditional_edges = {
                _NodeEnum.TOOLS: _NodeEnum.TOOLS,
                _NodeEnum.FORMAT: _NodeEnum.FORMAT,
            }
            builder.add_edge(_NodeEnum.TOOLS, _NodeEnum.CHAT)
        else:
            conditional_edges = {
                _NodeEnum.FORMAT: _NodeEnum.FORMAT,
            }

        builder.add_conditional_edges(
            _NodeEnum.CHAT,
            _router_node,
            conditional_edges,
        )
        builder.add_edge(_NodeEnum.FORMAT, END)

        self.agent = builder.compile(checkpointer=cfg.checkpointer)
        LOGGER.debug("Схема графа (Mermaid):\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, text: str, config: dict) -> BaseModel:
        """Метод-обёртка для отправки запросов LLM-агенту извне."""

        result = self.agent.invoke(
            input={"messages": [HumanMessage(text)]},
            config=config,
        )
        model = result["response"]

        if not isinstance(model, BaseModel):
            raise TypeError("Ответ агента не является моделью Pydantic")

        return model


class WordItem(BaseModel):
    """
    Отдельное слово итогового ответа.
    ? переделать под формат шагов Сценария
    """

    word: str = Field(..., description="Слово из итогового ответа.")


class JsonResponse(BaseModel):
    """
    Структура JSON-ответа.
    ? переделать под формат шагов Сценария
    """

    status: str = Field(..., description="Статус ответа: 'OK' или 'ERROR'.")
    message: str = Field(..., description="Текстовое сообщение для пользователя.")
    data: dict[str, Any] = Field(default_factory=dict, description="Словарь с техническими данными.")
    words: list[WordItem] = Field(
        default_factory=list,
        description="Массив слов итогового ответа.",
    )


class _OrchestratorState(MessagesState, total=False):
    """
    Состояние графа оркестратора.
    # ! [AI Note] Не добавлять в документацию
    """

    steps: int
    query: str
    documents: list[Document] | None
    response: JsonResponse


class _NodeEnum(StrEnum):
    """
    Имена узлов графа с инструментами.
    # ! [AI Note] Не добавлять в документацию
    """

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"


def _extract_query(messages) -> str:
    """
    Достаёт последний пользовательский запрос из истории (требование GigaChat?).
    ! [AI Note] Не добавлять в документацию
    """
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)

    last = messages[-1] if messages else None
    return str(getattr(last, "content", "") or "")


def _prepare_context_documents(docs: list[Document] | None) -> str:
    """
    Формирует текст контекста из найденных документов.
    ! [AI Note] Не добавлять в документацию
    """
    if not docs:
        return ""

    # ? нет поля source, как сделать по-другому
    # Для отладки: какие документы и их фрагменты вошли в контекст
    LOGGER.debug(
        "Контекст собран из %d документов:\n%s",
        len(docs),
        "\n".join(f"- {doc.metadata.get('source', '-')} [{len(doc.page_content)} симв.]" for doc in docs),
    )
    return "\n\n".join(
        f"<source>{doc.metadata.get('source', '-')}</source><content>{doc.page_content}</content>"
        for doc in docs
    )
