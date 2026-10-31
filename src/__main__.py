import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from src.agent import ScenarAIstAgent
from src.ui import Invoke, UserInterface

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
        LOGGER.debug(_redact(raw_cfg))

        agent = ScenarAIstAgent(raw_cfg)
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

    def invoke(self, text: str, config: dict) -> BaseModel:
        return self._agent.invoke(text, config)


# ! проверить
#: Имена ключей конфигурации, значения которых считаются секретами.
_SECRET_KEYS = (
    "api_key",
    "apikey",
    "token",
    "password",
    "secret",
    "credential",
)

#: Вхождения вида {api-key=...}, {token=...} внутри строковых значений.
_SECRET_VALUE_RE = re.compile(
    r"\{[^{}]*\b(?:api[_-]?key|apikey|token|password|secret|credential)\b[^{}]*=[^{}]*\}",
    re.IGNORECASE,
)


def _is_secret_key(key: str) -> bool:
    """Совпадает ли имя ключа с названием секрета (`api_key`, `API-Key`, ...)."""
    normalized = str(key).strip().lower().replace("-", "_")
    return any(part in normalized for part in _SECRET_KEYS)


def _redact(value: Any) -> Any:
    """Рекурсивно маскирует секреты в конфиге для безопасного логирования."""
    if isinstance(value, dict):
        return {key: "***" if _is_secret_key(key) else _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE_RE.sub("***", value)
    return value


if __name__ == "__main__":
    """Запуск как модуль"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format=LOG_FORMAT,
    )
    raise SystemExit(main())
