import logging
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.agent.agent import ScenarAIstAgent
from src.agent.model import ScenarAIstModelFactory
from src.ui.handler import InvokeAgent, UserInterface

LOG_FILE = "scenarAIst.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_BLANK_LINE = "=" * 26

APP_CONFIG_FILE = Path("config.yaml")
APP_WITH_WRITE_RESPONSE = True

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Запуск как приложение"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format=LOG_FORMAT,
    )
    LOGGER.info("\n%s\n%s\n%s", LOG_BLANK_LINE, "=== Запуск СценарИИста ===", LOG_BLANK_LINE)

    with APP_CONFIG_FILE.open(encoding="utf-8") as f:
        raw_cfg = yaml.safe_load(f)

    try:
        model = ScenarAIstModelFactory(raw_cfg)
    except Exception as e:
        LOGGER.critical(e)
        return -1

    agent = ScenarAIstAgent(model)
    agent.build()
    invoker = ImplInvoke(agent)
    ui = UserInterface(sys.argv, invoker, APP_WITH_WRITE_RESPONSE)

    try:
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

    def invoke(self, text: str) -> BaseModel:
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
