import logging
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.agent import ScenarAIstAgent
from src.agent.model import ScenarAIstModelFactory
from src.ui.handler import Invoke, UserInterface

CONFIG_FILE = Path("config.yaml")
LOG_FILE = "scenarAIst.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Запуск как приложение"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format=LOG_FORMAT,
    )
    LOGGER.info("Запуск СценарИИста")

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
