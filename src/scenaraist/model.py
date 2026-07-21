import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_gigachat import GigaChat, GigaChatEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_openrouter import ChatOpenRouter

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Provider:
    """TODO"""

    chat: Callable[[], BaseChatModel] | None = None
    embeddings: Callable[[], Embeddings] | None = None


# TODO найди здесь переменные окружения и запиши их в .env.example
PROVIDERS: dict[str, Provider] = {
    "gigachat": Provider(
        chat=lambda: GigaChat(
            credentials=_env("GIGACHAT_CREDENTIALS"),
            model=_env("GIGACHAT_MODEL", "GigaChat-2"),
            verify_ssl_certs=_env_bool("GIGACHAT_VERIFY_SSL_CERTS"),
            timeout=60,
        ),
        embeddings=lambda: GigaChatEmbeddings(
            credentials=_env("GIGACHAT_CREDENTIALS"),
            model=_env("GIGACHAT_EMBEDDING_MODEL", "Embeddings"),
        ),
    ),
    "openrouter": Provider(
        chat=lambda: ChatOpenRouter(
            api_key=_env("OPENROUTER_API_KEY"),
            model=_env("OPENROUTER_MODEL", "openrouter/free"),
            timeout=60,
        ),
    ),
    "openai": Provider(
        chat=lambda: ChatOpenAI(
            base_url=_env("OPENAI_BASE_URL", "https://api.ofox.ai/v1"),
            api_key=_env("OPENAI_API_KEY"),
            model=_env("OPENAI_MODEL", "z-ai/glm-4.7-flash:free"),
            timeout=60,
        ),
        embeddings=lambda: OpenAIEmbeddings(
            base_url=_env("OPENAI_BASE_URL", "https://api.ofox.ai/v1"),
            api_key=_env("OPENAI_API_KEY"),
            model=_env("OPENAI_EMBEDDING_MODEL"),
        ),
    ),
    "huggingface": Provider(
        embeddings=lambda: HuggingFaceEmbeddings(
            model_name=_env(
                "HUGGINGFACE_EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            ),
        ),
    ),
}


def _env(name: str, default: str | None = None) -> str:
    """TODO"""

    # TODO добавить проверку обязательности переменной окружения
    # для остановки программы при отсутствии переменной окружения
    return os.getenv(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    """TODO"""

    return os.getenv(name, str(default)).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_chat_model(provider: str) -> BaseChatModel:
    """TODO"""

    factory = PROVIDERS[provider].chat
    if factory is None:
        raise ValueError("Провайдер '%s' не поддерживает чат.", provider)
    LOGGER.info("Выбран провайдер чата: %s", provider)
    return factory()


def get_embeddings(provider: str) -> Embeddings:
    """TODO"""

    factory = PROVIDERS[provider].embeddings
    if factory is None:
        raise ValueError("Провайдер '%s' не поддерживает эмбеддинги.", provider)
    LOGGER.info("Выбран провайдер эмбеддингов: %s", provider)
    return factory()
