"""
Пакет "Пользовательский интерфейс".
Управление пользовательским интерфейсом, бизнес-логика.
"""

from importlib.metadata import version
from pathlib import Path

__version__ = version("scenaraist")

QML_DIR = Path(__file__).parent / "qml"
QML_MAIN_PATH = QML_DIR / "Main.qml"
