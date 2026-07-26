"""Конфигурация и фабрики провайдеров LLM и эмбеддингов."""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_gigachat import GigaChat, GigaChatEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_openrouter import ChatOpenRouter

LOGGER = logging.getLogger(__name__)


class IChat(Protocol):
    """Интерфейс фабрики для создания моделей чата."""

    def __call__(self) -> BaseChatModel: ...


class IEmbeddings(Protocol):
    """Интерфейс фабрики для создания моделей эмбеддингов."""

    def __call__(self) -> Embeddings: ...


@dataclass(frozen=True, slots=True)
class Provider:
    """Класс-провайдер LLM, содержащий фабрики для чата и эмбеддингов."""

    chat: IChat | None = None
    embeddings: IEmbeddings | None = None


class ProviderName(Enum):
    """Перечисление поддерживаемых провайдеров LLM."""

    GigaChat = Provider(
        chat=lambda: GigaChat(
            credentials=os.getenv("GIGACHAT_CREDENTIALS"),
            model=os.getenv("GIGACHAT_MODEL", "GigaChat-2"),
            verify_ssl_certs=os.getenv("GIGACHAT_VERIFY_SSL_CERTS", str(False)).strip().lower()
            in {"1", "true", "yes", "on"},
            timeout=60,
        ),
        embeddings=lambda: GigaChatEmbeddings(
            credentials=os.getenv("GIGACHAT_CREDENTIALS"),
            model=os.getenv("GIGACHAT_EMBEDDING_MODEL", "Embeddings"),
        ),
    )
    OpenRouter = Provider(
        chat=lambda: ChatOpenRouter(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            timeout=60,
        ),
    )
    OpenAI = Provider(
        chat=lambda: ChatOpenAI(
            base_url=os.getenv("OPENAI_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL"),
            timeout=60,
        ),
        embeddings=lambda: OpenAIEmbeddings(
            base_url=os.getenv("OPENAI_EMBEDDING_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_EMBEDDING_MODEL"),
        ),
    )
    HuggingFace = Provider(
        embeddings=lambda: HuggingFaceEmbeddings(
            model_name=os.getenv("HUGGINGFACE_EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"),
        ),
    )

    def get_chat(self) -> BaseChatModel:
        """Создать модель чата провайдера."""
        LOGGER.info("Выбран провайдер чата: %s", self.name)

        factory = self.value.chat
        if factory is None:
            raise KeyError(f"Провайдер '{self.name}' не поддерживает чат.")
        return factory()

    def get_embeddings(self) -> Embeddings:
        """Создать модель эмбеддингов провайдера."""
        LOGGER.info("Выбран провайдер эмбеддингов: %s", self.name)

        factory = self.value.embeddings
        if factory is None:
            raise KeyError(f"Провайдер '{self.name}' не поддерживает эмбеддинги.")
        return factory()
