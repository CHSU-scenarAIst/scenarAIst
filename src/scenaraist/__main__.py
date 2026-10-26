"""Оркестрация системы: логирование, сборка LLM-агента, чтение файла конфигурации."""

import logging
import sys
from pathlib import Path

import yaml
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from scenaraist.agent import ScenarAIstAgentBuilder
from scenaraist.handler import HandlerBackend

LOGGER = logging.getLogger(__name__)

QML_DIR = Path(__file__).parent / "qml"
QML_MAIN_PATH = QML_DIR / "Main.qml"
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
        cfg = yaml.safe_load(f)
    LOGGER.debug(cfg)

    try:
        agent = ScenarAIstAgentBuilder(cfg)
    except Exception as e:
        LOGGER.exception(e)
        return -1

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    # engine.addImportPath(sys.path[0])
    engine.addImportPath(QML_DIR)

    handler_backend = HandlerBackend(agent)
    engine.rootContext().setContextProperty("handlerBackend", handler_backend)
    engine.load(QML_MAIN_PATH)

    if not engine.rootObjects():
        LOGGER.exception("Нет объектов для отрисовки")
        return -2

    exit_code = app.exec()
    LOGGER.info("Завершение работы...")
    del engine
    return exit_code


if __name__ == "__main__":
    """Запуск как модуль"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format=LOG_FORMAT,
    )
    raise SystemExit(main())
