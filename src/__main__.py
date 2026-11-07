import logging
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.agent.agent import ScenarAIstAgent
from src.agent.model import ScenarAIstModelFactory
from src.ui.handler import Invoke, UserInterface

CONFIG_FILE = Path("config.yaml")
LOG_FILE = "scenarAIst.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
BLANK_LINE = "=" * 26

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Запуск как приложение"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format=LOG_FORMAT,
    )
    LOGGER.info("\n%s\n%s\n%s", BLANK_LINE, "=== Запуск СценарИИста ===", BLANK_LINE)

    try:
        with CONFIG_FILE.open(encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f)
            LOGGER.debug(raw_cfg)

        cfg = ScenarAIstModelFactory(raw_cfg)
        agent = ScenarAIstAgent(cfg)
        agent.build()
        invoker = ImplInvoke(agent)
        ui = UserInterface(invoker)
        exit_code = ui.run()
    except Exception as e:
        LOGGER.exception(e)
        return -1

    LOGGER.info("\n%s\n%s\n%s", BLANK_LINE, "== Завершение работы... ==", BLANK_LINE)
    return exit_code


class ImplInvoke(Invoke):
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
    raise SystemExit(main())
