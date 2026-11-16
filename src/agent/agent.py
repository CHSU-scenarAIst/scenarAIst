"""Сборка LLM-агента с инструментами и структурированным выводом.
- Получение Json-Сценария на вход (back_request).
- Ручная сборка ответа в Json
"""

import logging
from datetime import UTC, datetime
from typing import Any

from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import ValidationError

from src.agent.model import AgentModelFactory
from src.agent.schema import AgentResponse, AgentState, BackRequest, Scenario
from src.agent.tools import AgentToolsBuilder

LOGGER = logging.getLogger(__name__)


class ScenarAIstAgent:
    """Сборщик агента-Сценариста."""

    def __init__(self, model: AgentModelFactory, data: dict[str, str]):
        self._tools = AgentToolsBuilder().build(data=data)  # * Инструменты агента
        self._agent_llm = model.chat.bind_tools(self._tools)  # * Агент-Сценарист
        self._system_prompt = (
            SYSTEM_PROMPT + "<user>" + model.chat_cfg.system_prompt + "</user>"
        )  # * Главные инструкции агента
        self._retrievers = model.retrievers  # * Обработчики эмбеддингов документов
        self._max_invokes = model.chat_cfg.max_invokes  # * Максимальное число вызовов в одном ответе агента.
        LOGGER.info(model.chat_cfg.model_dump_json())

    def build(self) -> None:
        """Сборка LLM-агента."""

        builder = StateGraph(AgentState)
        builder.add_node(CHAT_NODE, self._chat_node)
        builder.add_node(FORMAT_NODE, self._format_node)

        if self._retrievers:
            builder.add_node(RETRIVE_NODE, self._retrieve_node)
            builder.add_edge(START, RETRIVE_NODE)
            builder.add_edge(RETRIVE_NODE, CHAT_NODE)
        else:
            builder.add_edge(START, CHAT_NODE)

        conditional_edges = [FORMAT_NODE, CHAT_NODE]
        if self._tools:
            tool_node = ToolNode(self._tools)
            builder.add_node(TOOL_NODE, tool_node)
            builder.add_edge(TOOL_NODE, CHAT_NODE)
            conditional_edges.append(TOOL_NODE)

        builder.add_conditional_edges(CHAT_NODE, self._router_node, conditional_edges)
        builder.add_edge(FORMAT_NODE, END)

        self.agent = builder.compile()
        LOGGER.debug("StateGraph (mermaid)\n%s", self.agent.get_graph().draw_mermaid())

    def invoke(self, task: str, min_steps: int, instruct: str) -> AgentResponse:
        """API для отправки запросов LLM-агенту."""

        LOGGER.info("[invoke] -- Task: '%.40s...', min_step: '%s', instruct: '%s'", task, min_steps, instruct)
        self._min_steps = min_steps
        scenario = Scenario()
        try:
            back_request = BackRequest.model_validate_json(task)
        except ValidationError:
            LOGGER.info("Task is not 'back_request'.")
            task += f"<instruct>{instruct}</instruct>" if instruct else ""
        else:
            if back_request.steps:
                task = instruct
                scenario = Scenario(steps=back_request.steps)
                scenario.rebuild_indexes()
                LOGGER.info("Recived Scenario from 'back_request': %d Steps.", scenario.count())
            else:
                return AgentResponse(query=task, answer="Передан пустой Сценарий")

        state: AgentState = {
            "messages": [SystemMessage(self._system_prompt), HumanMessage(task)],
            "query": task,
            "sources": {},
            "scenario": scenario,
            "invokes_count": 0,
            "invokes_max": self._max_invokes,
        }
        LOGGER.debug(LOG_PATTERN, "Start AgentState", state)

        response = self.agent.invoke(input=state)
        result = response["result"]
        return AgentResponse.model_validate(result)

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    def _retrieve_node(self, state: AgentState) -> dict[str, Any]:
        """Узел поиска релевантных документов по запросу. # ? NOTTODO доделать"""
        query = state["query"]
        docs = [doc for r in self._retrievers for doc in r.invoke(query)]
        LOGGER.info(
            "Контекст собран из %d документов:\n%s",
            len(docs),
            "\n".join(f"- {d} [{len(d.page_content)} симв.]" for d in docs),
        )
        sources = {
            i: {
                "source": f"<source>{d.metadata.get('source', '-')}</source>",
                "content": f"<content>{d.page_content}</content>",
            }
            for i, d in enumerate(docs, start=1)
        }
        LOGGER.info(LOG_PATTERN, RETRIVE_NODE, sources)
        return {"invokes_count": 1, "sources": sources}

    def _chat_node(self, state: AgentState) -> dict[str, Any]:
        """Узел генерации ответа агентом."""
        prompt = [*state["messages"], HumanMessage(str(state["sources"]))]
        if self._min_steps > state["scenario"].count():
            sys_mes = HumanMessage(
                "<system>Scenario is not complete! Use tool 'insert_step' to add some Steps.</system>"
            )
            prompt.append(sys_mes)

        response = self._agent_llm.invoke(prompt)
        LOGGER.info(LOG_PATTERN, CHAT_NODE, str(response.content).strip())
        return {"invokes_count": 1, "messages": [response]}

    def _router_node(self, state: AgentState) -> str:
        """Ветвление графа."""
        last_message = state["messages"][-1]
        invokes_count = state["invokes_count"]
        invokes_max = state["invokes_max"]

        if self._tools and getattr(last_message, "tool_calls", []):
            if invokes_count < invokes_max:
                LOGGER.info(LOG_ROUTE, f"{invokes_count}/{invokes_max}", TOOL_NODE)
                return TOOL_NODE

            LOGGER.info(LOG_ROUTE, f"{invokes_count}/{invokes_max}", FORMAT_NODE)
            return FORMAT_NODE

        if self._min_steps > state["scenario"].count():
            LOGGER.info(LOG_ROUTE, invokes_count, CHAT_NODE)
            return CHAT_NODE

        LOGGER.info(LOG_ROUTE, f"{invokes_count}/{invokes_max}", FORMAT_NODE)
        return FORMAT_NODE

    def _format_node(self, state: AgentState) -> dict[str, Any]:
        """Узел финализации ответа в JSON-структуру."""
        last_message = state["messages"][-1]
        result = AgentResponse(
            query=state["query"],
            answer=str(last_message.content),
            sources=state["sources"],
            steps=state["scenario"].serialize_steps(),
        )
        LOGGER.info(LOG_PATTERN, FORMAT_NODE, result)
        return {"result": result, "invokes_count": 1}


LOG_PATTERN = "[%s] -- %s"
LOG_ROUTE = "[%s] --> [%s]"
RETRIVE_NODE = "retrieve_node"
CHAT_NODE = "chat_node"
TOOL_NODE = "tool_node"
FORMAT_NODE = "format_node"

SYSTEM_PROMPT = (
    "<system>"
    "- The purpose of your existence is to process behavioral instructions for personnel"
    " in a production environment, which will be used in VR training simulations."
    " These personnel instructions are referred to as 'Scenarios.'"
    "- A **Scenario** in a VR simulator is a structured sequence of discrete actions"
    " performed by personnel; it encompasses information regarding the situation, the environment,"
    " the individuals involved, the actions to be taken, and the available choices."
    "- If there is no data available for generation, you are required to state this."
    "- You still have the opportunity to talk about various topics."
    "</system>"
    f"<time_now>{datetime.now(UTC):%B %d, %Y}.</time_now>"
    "<tools>Tool Usage Policy"
    "- **Scenario Creation:** Whenever the user asks to create, generate, or build a scenario,"
    " you **MUST** use the available tools."
    "- **No Direct Generation:** Never write an answer directly in your text response"
    " without executing the corresponding tool call first."
    "- When working with tools, always consider their output to be true and final."
    "- Before modifying a Scenario, always retrieve its current state."
    "</tools>"
)
