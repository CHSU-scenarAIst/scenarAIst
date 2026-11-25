"""Сборка LLM-агента с инструментами и структурированным выводом.
- Получение Json-Сценария на вход (back_request).
- Ручная сборка ответа в Json.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Self

from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from src.agent.model import AgentModelBuilder
from src.agent.tools import AgentState, AgentToolsBuilder

LOGGER = logging.getLogger(__name__)


class ScenarAIstAgent:
    """АгентСценарист. Модель ИИ-Сценариста."""

    def __init__(self) -> None:
        model = AgentModelBuilder().build()
        self._tools = AgentToolsBuilder().build(data=model.actions_data)  # * Инструменты агента.
        self._agent_llm = model.chat.bind_tools(self._tools)  # * Агент-Сценарист.
        self._system_prompt = (
            SYSTEM_PROMPT + "<user>" + model.chat_cfg.system_prompt + "</user>"
        )  # * Главные инструкции агента
        self._retrievers = model.retrievers  # * Обработчики эмбеддингов документов.
        self._max_invokes = model.chat_cfg.max_invokes  # * Максимальное число вызовов в одном ответе агента.
        LOGGER.info(model.chat_cfg.model_dump_json())
        if e_cfg := model.embed_cfg:
            LOGGER.info(e_cfg.model_dump_json())

    def build(self) -> Self:
        """Сборка ИИ-агента."""

        builder = StateGraph(AgentState)
        builder.add_node(CHAT_NODE, self._chat_node)

        if self._retrievers:
            builder.add_node(RETRIVE_NODE, self._retrieve_node)
            builder.add_edge(START, RETRIVE_NODE)
            builder.add_edge(RETRIVE_NODE, CHAT_NODE)
        else:
            builder.add_edge(START, CHAT_NODE)

        conditional_edges = [END, CHAT_NODE]
        if self._tools:
            tool_node = ToolNode(self._tools)
            builder.add_node(TOOL_NODE, tool_node)
            builder.add_edge(TOOL_NODE, CHAT_NODE)
            conditional_edges.append(TOOL_NODE)

        builder.add_conditional_edges(CHAT_NODE, self._router_node, conditional_edges)

        self.agent = builder.compile()
        LOGGER.debug("StateGraph (mermaid)\n%s", self.agent.get_graph().draw_mermaid())
        return self

    def invoke(self, task: str, min_steps: int, instruct: str) -> str:
        """API для отправки запросов ИИ-агенту."""

        LOGGER.info(
            "[invoke] -- Task: '%.90s...', min_step: '%s', instruct: '%s'",
            task,
            min_steps,
            instruct,
        )
        self._min_steps = min_steps  # * Минимальное число Шагов в Сценарии.
        try:
            state = AgentState.from_back_request(task, instruct)
            if (count := state.response.count_steps()) <= 0:
                return state.response.serialize()
            LOGGER.info("Recived Scenario from 'back_request': %d Steps.", count)
        except Exception:
            LOGGER.info("Task is not 'back_request'.")
            task += f"<instruct>{instruct}</instruct>" if instruct else ""
            state = AgentState.from_task(task)

        state.messages = [SystemMessage(self._system_prompt), HumanMessage(task)]
        state.invokes_max = self._max_invokes
        LOGGER.debug(LOG_PATTERN, "Start AgentState", state)
        data = self.agent.invoke(input=state)

        response = AgentState.model_validate(data)
        scenario = response.response.model_copy(deep=True).serialize()
        LOGGER.info(LOG_PATTERN, "invoke", scenario)
        return scenario

    # ! [AI Note] Секция не_добавлять_в / удалить_из документации
    def _retrieve_node(self, state: AgentState) -> dict[str, Any]:
        response = state.response.model_copy(deep=True)
        docs = [doc for r in self._retrievers for doc in r.invoke(response.query)]
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
        response.sources = sources
        LOGGER.info(LOG_PATTERN, RETRIVE_NODE, sources)
        return {
            "response": response,
            "invokes_count": 1,
        }

    def _chat_node(self, state: AgentState) -> dict[str, Any]:
        response = state.response.model_copy(deep=True)
        prompt = [*state.messages, HumanMessage(str(response.sources))]
        if self._min_steps > response.count_steps():
            mes = "<system>Scenario is not complete! Use tool 'insert_step' to add some Steps.</system>"
            sys_mes = HumanMessage(mes)
            prompt.append(sys_mes)
        result = self._agent_llm.invoke(prompt)
        last_message = str(result.content)
        response.answer = last_message
        LOGGER.info(LOG_PATTERN, CHAT_NODE, last_message.strip())
        return {
            "messages": [result],
            "response": response,
            "invokes_count": 1,
        }

    def _router_node(self, state: AgentState) -> str:
        invokes_count = state.invokes_count
        invokes_max = state.invokes_max
        if self._tools and getattr(state.messages[-1], "tool_calls", []):
            if invokes_count < invokes_max:
                LOGGER.info(LOG_ROUTE, f"{invokes_count}/{invokes_max}", TOOL_NODE)
                return TOOL_NODE

            LOGGER.info(LOG_ROUTE, f"{invokes_count}/{invokes_max}", END)
            return END

        if self._min_steps > state.response.count_steps():
            LOGGER.info(LOG_ROUTE, invokes_count, CHAT_NODE)
            return CHAT_NODE

        LOGGER.info(LOG_ROUTE, f"{invokes_count}/{invokes_max}", END)
        return END


LOG_PATTERN = "[%s] -- %s"
LOG_ROUTE = "[%s] --> [%s]"
RETRIVE_NODE = "retrieve_node"
CHAT_NODE = "chat_node"
TOOL_NODE = "tool_node"

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
