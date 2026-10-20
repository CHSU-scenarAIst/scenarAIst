"""Сборка и компиляция графа LangGraph."""

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from langchain.chat_models import BaseChatModel
from langchain.messages import HumanMessage, SystemMessage
from langchain.tools import BaseTool
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState
from langgraph.graph.state import StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


# TODO with_structured_output()
class AgentGraphBuilder:
    """Объектный сборщик и компилятор графа LangGraph."""

    def __init__(
        self,
        chat: BaseChatModel,
        system_prompt: str,
        max_steps: int,
        checkpointer: BaseCheckpointSaver,
        tools: list[BaseTool] | None = None,
        retriever: list[BaseRetriever] | None = None,
    ):
        self._chat = chat
        self._system_prompt = system_prompt
        self._checkpointer = checkpointer
        self._tools = tools or []
        self._retriever = retriever
        self._max_steps = max_steps

    def compile(self):
        """Собрать и скомпилировать граф состояний агента."""
        agent_llm = self._chat.bind_tools(self._tools)

        def retrieve_node(state: OrchestratorState):
            """Узел поиска релевантных документов по запросу."""
            LOGGER.info("%s", retrieve_node)

            if not self._retriever:
                return {
                    "query": "",
                    "documents": [],
                    "steps": state.get("steps", 0) + 1,
                }

            query = self.extract_query(state["messages"])
            docs = [doc for r in self._retriever for doc in r.invoke(query)]

            return {
                "query": query,
                "documents": docs,
                "steps": state.get("steps", 0) + 1,
            }

        def chat_node(state: OrchestratorState):
            """Узел вызова LLM с текущей историей сообщений."""
            messages = state["messages"]
            LOGGER.info("%s with %d messages", chat_node, len(messages))

            docs = state.get("documents", None)
            system_content = self._system_prompt + f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"

            if context := self.prepare_context_documents(docs):
                system_content += f"<context>{context}</context>"

            response = agent_llm.invoke([SystemMessage(system_content), *messages])
            LOGGER.info("LLM response: response=%s", response)

            return {
                "messages": [response],
                "steps": state.get("steps", 0) + 1,
            }

        def router_node(state: OrchestratorState):
            """Ветвление после вызова LLM: исполнение инструментов либо финализация ответа."""
            LOGGER.info("%s", router_node)

            last = state["messages"][-1]
            tool_calls = getattr(last, "tool_calls", [])

            if tool_calls and self._tools and state.get("steps", 0) < self._max_steps:
                return NodeEnum.TOOLS

            return NodeEnum.FORMAT

        tool_node = ToolNode(self._tools)

        def tools_node(state: OrchestratorState):
            """Узел исполнения инструментов, выбранных LLM."""
            LOGGER.info("%s", tools_node)

            result = tool_node.invoke(state)
            return {
                **result,
                "steps": state.get("steps", 0) + 1,
            }

        def format_node(state: OrchestratorState):
            """Узел финализации ответа в JSON-структуру."""
            LOGGER.info("%s", format_node)

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

        builder = StateGraph(OrchestratorState)

        # * Структура графа
        builder.add_node(NodeEnum.CHAT, chat_node)
        builder.add_node(NodeEnum.FORMAT, format_node)

        if self._retriever:
            LOGGER.info("%s +", NodeEnum.RETRIEVE)
            builder.add_node(NodeEnum.RETRIEVE, retrieve_node)
            builder.add_edge(START, NodeEnum.RETRIEVE)
            builder.add_edge(NodeEnum.RETRIEVE, NodeEnum.CHAT)
        else:
            LOGGER.info("%s -", NodeEnum.RETRIEVE)
            builder.add_edge(START, NodeEnum.CHAT)

        if self._tools:
            builder.add_node(NodeEnum.TOOLS, tools_node)
            conditional_edges = {
                NodeEnum.TOOLS: NodeEnum.TOOLS,
                NodeEnum.FORMAT: NodeEnum.FORMAT,
            }
            builder.add_edge(NodeEnum.TOOLS, NodeEnum.CHAT)
        else:
            conditional_edges = {
                NodeEnum.FORMAT: NodeEnum.FORMAT,
            }

        builder.add_conditional_edges(
            NodeEnum.CHAT,
            router_node,
            conditional_edges,
        )
        builder.add_edge(NodeEnum.FORMAT, END)

        # * Компиляция агента
        agent = builder.compile(checkpointer=self._checkpointer)
        # ? debug схемы структуры графа в MarkDown
        LOGGER.info("Граф скомпилирован")
        return agent

    def extract_query(self, messages) -> str:
        """Достаёт последний пользовательский запрос из истории (требование GigaChat?)."""
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return str(message.content)

        last = messages[-1] if messages else None
        return str(getattr(last, "content", "") or "")

    def prepare_context_documents(self, docs: list[Document] | None) -> str:
        """Формирует текст контекста из найденных документов."""
        if not docs:
            return ""
        # ! source нет такого поля
        # TODO debug что в документах
        return "\n\n".join(
            f"<source>{doc.metadata.get('source', '-')}</source><content>{doc.page_content}</content>"
            for doc in docs
        )


class WordItem(BaseModel):
    """Отдельное слово итогового ответа."""

    word: str = Field(..., description="Слово из итогового ответа.")


class JsonResponse(BaseModel):
    """Структура JSON-ответа."""

    status: str = Field(..., description="Статус ответа: 'OK' или 'ERROR'.")
    message: str = Field(..., description="Текстовое сообщение для пользователя.")
    data: dict[str, Any] = Field(default_factory=dict, description="Словарь с техническими данными.")
    words: list[WordItem] = Field(
        default_factory=list,
        description="Массив слов итогового ответа.",
    )


class OrchestratorState(MessagesState, total=False):
    """Состояние графа оркестратора."""

    steps: int
    query: str
    documents: list[Document] | None
    response: JsonResponse


class NodeEnum(StrEnum):
    """Имена узлов графа с инструментами."""

    RETRIEVE = "retrieve_node"
    CHAT = "chat_node"
    TOOLS = "tool_node"
    FORMAT = "format_node"
