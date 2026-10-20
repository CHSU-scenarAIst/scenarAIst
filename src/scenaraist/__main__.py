"""Точка входа scenarAIst."""

import logging
import sys
from pathlib import Path

import yaml
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from scenaraist.agent import AgentGraphBuilder
from scenaraist.handler import HandlerBackend
from scenaraist.model import get_model

LOGGER = logging.getLogger(__name__)
QML_DIR = Path(__file__).parent / "qml"
CONFIG_FILE = Path("config.yaml")
LOG_FILE = "scenarAIst.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def main() -> int:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format=LOG_FORMAT,
    )

    with CONFIG_FILE.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    LOGGER.debug(cfg)

    chat, system_prompt, max_steps, checkpointer, retriever, tools = get_model(cfg)

    agent = AgentGraphBuilder(
        chat=chat,
        system_prompt=system_prompt,
        max_steps=max_steps,
        checkpointer=checkpointer,
        retriever=retriever,
        tools=tools,
    ).compile()

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    # ? engine.addImportPath(sys.path[0])
    engine.addImportPath(QML_DIR)

    # * QML-фронтенд
    handler_backend = HandlerBackend(agent)
    engine.rootContext().setContextProperty("handlerBackend", handler_backend)
    engine.load(QML_DIR / "Main.qml")

    if not engine.rootObjects():
        return -1

    exit_code = app.exec()
    LOGGER.info("Завершение работы...")
    del engine
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format=LOG_FORMAT,
    )
    LOGGER.info("Запуск СценарИИста")
    raise SystemExit(main())
