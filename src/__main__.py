import logging
import sys
from pathlib import Path

import yaml

from src.agent.agent import ScenarAIstAgent
from src.agent.model import AgentModelFactory
from src.agent.schema import AgentResponse
from src.ui.handler import InvokeAgent, UserInterface

LOGGER = logging.getLogger(__name__)

# APP_WITH_WRITE_RESPONSE = True


def main(with_write_response: bool = True) -> int:
    """Запуск как приложение"""
    logging.basicConfig(
        filename="log-scenarAIst.log",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    log_blank_line = "=" * 26
    LOGGER.info("\n%s\n%s\n%s", log_blank_line, "=== Запуск СценарИИста ===", log_blank_line)

    try:
        with Path("config.yaml").open(encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f)

        model = AgentModelFactory(raw_cfg)

        with Path(model.chat_cfg.actions_path).open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or not data:
            raise ValueError("Файл действий должен содержать непустой словарь.")

        agent = ScenarAIstAgent(model, data)
        agent.build()
        invoker = ImplInvoke(agent)
        ui = UserInterface(sys.argv, invoker, with_write_response)
        exit_code = ui.run()
    except Exception as e:
        LOGGER.critical(e)
        return -1

    LOGGER.info("\n%s\n%s\n%s", log_blank_line, "== Завершение работы... ==", log_blank_line)
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
        filename="log-debug.log",
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # APP_WITH_WRITE_RESPONSE = False
    raise SystemExit(main(False))
