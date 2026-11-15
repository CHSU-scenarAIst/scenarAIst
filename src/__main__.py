import logging
import sys
from pathlib import Path

import yaml

from src.agent.agent import ScenarAIstAgent
from src.agent.model import AgentModelFactory
from src.agent.schema import AgentResponse
from src.ui.handler import InvokeAgent, UserInterface

LOGGER = logging.getLogger(__name__)

LOG_FILE = "scenarAIst.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_BLANK_LINE = "=" * 26

APP_CONFIG_FILE = Path("config.yaml")
APP_WITH_WRITE_RESPONSE = True
# ! Имитация получения действий персонала из базы данных действий
APP_ACTIONS_FILE = Path("actions.yaml")


def main() -> int:
    """Запуск как приложение"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format=LOG_FORMAT,
    )
    LOGGER.info("\n%s\n%s\n%s", LOG_BLANK_LINE, "=== Запуск СценарИИста ===", LOG_BLANK_LINE)

    try:
        with APP_CONFIG_FILE.open(encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f)
        with APP_ACTIONS_FILE.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or not data:
            raise ValueError("Файл действий должен содержать непустой словарь.")

        model = AgentModelFactory(raw_cfg)
        agent = ScenarAIstAgent(model, data)
        agent.build()
        invoker = ImplInvoke(agent)
        ui = UserInterface(sys.argv, invoker, APP_WITH_WRITE_RESPONSE)
        exit_code = ui.run()
    except Exception as e:
        LOGGER.critical(e)
        return -1

    LOGGER.info("\n%s\n%s\n%s", LOG_BLANK_LINE, "== Завершение работы... ==", LOG_BLANK_LINE)
    return exit_code


class ImplInvoke(InvokeAgent):
    """Реализация интерфейса `Invoke`."""

    def __init__(self, agent: ScenarAIstAgent):
        self._agent = agent

    def invoke(self, text: str) -> AgentResponse:
        return self._agent.invoke(text)


if __name__ == "__main__":
    """Запуск как модуль"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format=LOG_FORMAT,
    )
    APP_WITH_WRITE_RESPONSE = False
    raise SystemExit(main())
