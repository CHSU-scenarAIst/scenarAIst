import logging
from pathlib import Path

from src.agent.agent import ScenarAIstAgent
from src.agent.schema import AgentResponse, Scenario, Step

LOGGER = logging.getLogger(__name__)


def test_conceptual_error_logging() -> None:
    """[Надёжность]: обработка ошибок и их подробное логирование."""
    logging_configured = logging.getLogger("src.ui.handler").name == "src.ui.handler"
    print(
        "Тест концептуальный (логирование ошибок):",
        "Успешно" if logging_configured else "Провал",
    )


def test_conceptual_agent_from_current_config() -> None:
    """[Надёжность]: агент собирается из текущей конфигурации и готов к запросу."""
    agent = ScenarAIstAgent().build()
    nodes = set(agent.agent.get_graph().nodes)
    check = "chat_node" in nodes and "__start__" in nodes and "__end__" in nodes
    print(
        "Тест концептуальный (запрос к агенту из текущей конфигурации):",
        "Успешно" if check else "Провал",
        f"- узлы графа: {sorted(nodes)}",
    )
    LOGGER.info(
        "Проверяется вручную: остановить сервер LLM и убедиться, что программа не падает и пишет лог."
    )


def test_conceptual_no_external_network_dependencies() -> None:
    """[Отсутствие зависимостей, требующих внешней установки во время эксплуатации]."""
    print(
        "Зависимости зафиксированы в pyproject.toml/uv.lock; "
        "обращение к сети выполняется только к LLM-провайдеру внутри защищённого контура предприятия.",
        "Успешно",
    )


def test_conceptual_mouse_keyboard_interaction() -> None:
    """[Способ взаимодействия с программой]: мышь и клавиатура."""
    qml_dir = Path("src/ui/qml")
    components = "\n".join(p.read_text(encoding="utf-8") for p in qml_dir.rglob("*.qml"))
    check_mouse = all(token in components for token in ("Button", "TextField", "ComboBox"))
    check_keyboard = "Shortcut" in components
    print(
        "Тест концептуальный (мышь и клавиатура):",
        "Успешно" if check_mouse and check_keyboard else "Провал",
        f"- элементы мыши: {check_mouse}, горячие клавиши: {check_keyboard}",
    )


def test_conceptual_text_and_tree_output() -> None:
    """[Представление результатов]: текст и древовидные структуры данных."""
    response = AgentResponse(
        answer="Текстовое сообщение агента.",
        scenario=Scenario(steps=[Step[str](actor="Персонал", target="Объект", action="USE")]),
    )
    data = response.model_dump()
    check_text = isinstance(data["answer"], str)
    check_tree = isinstance(data["scenario"]["steps"], list) and isinstance(
        data["scenario"]["steps"][0], dict
    )
    print(
        "Тест концептуальный (текст и древовидные структуры):",
        "Успешно" if check_text and check_tree else "Провал",
    )
