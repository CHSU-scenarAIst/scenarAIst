import logging
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from agent import ScenarAIstAgent
from ui import QML_DIR
from ui.handler import HandlerBackend, Invoke

LOGGER = logging.getLogger(__name__)

UI_DIR = Path(__file__).parent / QML_DIR
CONFIG_FILE = Path("config.yaml")
LOG_FILE = "scenarAIst.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def main() -> int:
    """Запуск как приложение"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format=LOG_FORMAT,
    )
    LOGGER.info("Запуск СценарИИста")

    with CONFIG_FILE.open(encoding="utf-8") as f:
        raw_cfg = yaml.safe_load(f)
    LOGGER.debug(raw_cfg)

    try:
        agent = ScenarAIstAgent(raw_cfg)
        invoker = ImplInvoke(agent)
        handler_backend = HandlerBackend(invoker)
    except Exception as e:
        LOGGER.exception(e)
        return -1

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    # engine.addImportPath(sys.path[0])
    engine.addImportPath(QML_DIR)
    engine.rootContext().setContextProperty("handlerBackend", handler_backend)
    engine.load(QML_MAIN_PATH)

    if not engine.rootObjects():
        LOGGER.exception("Нет объектов для отрисовки")
        return -2

    exit_code = app.exec()
    del engine
    LOGGER.info("Завершение работы...")
    return exit_code


class ImplInvoke(Invoke):
    """Реализация интерфейса {@link Invoke}."""

    def __init__(self, agent: ScenarAIstAgent):
        self._agent = agent

    def invoke(self, text: str, config) -> BaseModel:
        return self._agent.invoke(text, config)


if __name__ == "__main__":
    """Запуск как модуль"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format=LOG_FORMAT,
    )
    raise SystemExit(main())
