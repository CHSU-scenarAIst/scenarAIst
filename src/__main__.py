import logging
import sys

from src.agent.agent import ScenarAIstAgent
from src.ui.handler import InvokeAgent, UserInterface

LOGGER = logging.getLogger(__name__)


def main(write_response: bool = True) -> int:
    """Запуск как приложение"""
    logging.basicConfig(
        filename="log-scenarAIst.log",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    blank_line = "=" * 26
    LOGGER.info("\n%s\n%s\n%s", blank_line, "=== Запуск СценарИИста ===", blank_line)

    try:
        agent = ScenarAIstAgent().build()
        invoker = ImplInvoke(agent)
        ui = UserInterface(sys.argv, invoker, write_response)
        exit_code = ui.run()
    except Exception as e:
        LOGGER.critical(e)
        return -1

    LOGGER.info("\n%s\n%s\n%s", blank_line, "== Завершение работы... ==", blank_line)
    return exit_code


class ImplInvoke(InvokeAgent):
    """Реализация интерфейса `Invoke`."""

    def __init__(self, agent: ScenarAIstAgent):
        self._agent = agent

    def invoke(self, task: str, min_steps: int, add_instruct: str) -> str:
        return self._agent.invoke(task, min_steps, add_instruct)


if __name__ == "__main__":
    """Запуск как модуль"""
    logging.basicConfig(
        filename="log-debug.log",
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    raise SystemExit(main(False))
