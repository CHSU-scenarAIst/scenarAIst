"""Сборщики LLM разных провайдеров.
- Настройка работы программы через конфигурационный файл.
    - Настройка модели Completion
    - Настройка модели Embedding
"""

import logging
from enum import StrEnum
from pathlib import Path
from typing import Protocol, Self

import yaml
from langchain.chat_models import BaseChatModel
from langchain.embeddings import Embeddings
from langchain_gigachat import GigaChat
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field, SecretStr

from src.agent.vec_db import CollectionConfig, VectoreStoreBuilder

LOGGER = logging.getLogger(__name__)


class AgentModelBuilder:
    """Сборщик LLM и обработчиков эмбеддингов разных провайдеров."""

    def __init__(self) -> None:
        with Path("config.yaml").open(encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f)

        try:
            self.chat_cfg = CompletionConfig.model_validate(raw_cfg["completion"])
        except Exception as e:
            raise TypeError("Ошибка конфигурации модели.") from e

        with Path(self.chat_cfg.actions_path).open(encoding="utf-8") as f:
            actions_data = yaml.safe_load(f)
        if not isinstance(actions_data, dict) or not actions_data:
            raise ValueError("Файл действий должен содержать непустой словарь.")
        self.actions_data: dict[str, str] = actions_data

        self.embed_cfg: EmbeddingConfig | None = None
        try:
            self.embed_cfg = EmbeddingConfig.model_validate(raw_cfg["embeddings"])
        except Exception:
            LOGGER.info("Нет внешних данных для подключения: 'embeddings'.")

    def build(self) -> Self:
        if (name := self.chat_cfg.provider.strip().lower()) not in CHAT_FACTORIES:
            raise TypeError(f"Ошибка загрузки 'completion' -> 'provider': '{name}'.")
        self.chat = CHAT_FACTORIES[name](self.chat_cfg)

        self.retrievers = []
        if self.embed_cfg:
            if (name := self.embed_cfg.provider.strip().lower()) not in EMBEDDING_FACTORIES:
                raise TypeError(f"Ошибка загрузки 'embeddings' -> 'provider': '{name}'.")
            embeddings = EMBEDDING_FACTORIES[name](self.embed_cfg)
            db = VectoreStoreBuilder(self.embed_cfg.db_path)
            db.build(embeddings, self.embed_cfg.collections)
            self.retrievers = db.retrivers
        return self


class Providers(StrEnum):
    """Перечисление доступных провайдеров LLM."""

    OPENAI = "openai"
    GIGACHAT = "gigachat"


# ! [AI Note] `CompletionConfig`, `EmbeddingConfig` и `CollectionConfig` в документации это
# ! один класс """.КонфигурацияПрограммы. Конфигурация работы программы и LLM."""
class CompletionConfig(BaseModel):
    """Конфигурация LLM генерации."""

    provider: Providers = Field(description="Провайдер LLM.")

    verify_ssl_certs: bool = Field(default=False, description="Проверять ли SSL-сертификаты.")
    base_url: str | None = Field(default=None, description="Путь API провайдера.")
    api_key: SecretStr = Field(default=SecretStr("SECRET"), description="Ключ API провайдера.")
    model: str | None = Field(default=None, description="Название LLM чата.")
    temperature: float = Field(default=0.1, description="Температура выборки токенов (0..1).")
    max_tokens: int = Field(default=10000, description="Максимальное число токенов в одном ответе агента.")
    max_invokes: int = Field(default=30, description="Максимальное число вызовов в одном ответе агента.")
    timeout: int = Field(default=60, description="Время ожидания ответа от запроса к API, в секундах.")
    system_prompt: str = Field(default="You are a helpful assistant.", description="Системный промпт.")
    actions_path: str = Field(default="./datasets/actions.yaml", description="Путь к Действиям персонала.")


class EmbeddingConfig(BaseModel):
    """Конфигурация LLM эмбеддингов и векторного хранилища."""

    provider: Providers = Field(description="Провайдер эмбеддингов.")

    base_url: str | None = Field(default=None, description="Путь API провайдера LLM эмбеддингов.")
    api_key: SecretStr = Field(default=SecretStr("SECRET"), description="Ключ API провайдера эмбеддингов.")
    model: str | None = Field(default=None, description="Название LLM эмбеддингов.")
    collections: list[CollectionConfig] = Field(default_factory=list, description="Список путей к папкам.")
    verify_ssl_certs: bool = Field(default=False, description="Проверять ли SSL-сертификаты.")
    dim: int = Field(default=1024, ge=1, description="Размерность вектора эмбеддинга.")
    db_path: str = Field(default="./rag.sqlite3", description="Путь к файлу векторной базы данных.")
    batch_size: int = Field(default=4, ge=1, description="Сколько документов обрабатывается за один запрос.")
    timeout: int = Field(default=60, description="Время ожидания ответа от запроса к API, в секундах.")


# ! [AI Note] Секция не_добавлять_в / удалить_из документации


class ICreateChat(Protocol):
    """Интерфейс фабрики для создания моделей чата."""

    def __call__(self, cfg: CompletionConfig) -> BaseChatModel: ...


class ICreateEmbeddings(Protocol):
    """Интерфейс фабрики для создания моделей эмбеддингов."""

    def __call__(self, cfg: EmbeddingConfig) -> Embeddings: ...


def _create_openai_compatible_chat(cfg: CompletionConfig) -> BaseChatModel:
    return ChatOpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "",
        temperature=cfg.temperature,
        max_completion_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def _create_gigachat_chat(cfg: CompletionConfig) -> BaseChatModel:
    return GigaChat(
        credentials=cfg.api_key.get_secret_value(),
        model=cfg.model or "GigaChat-2",
        verify_ssl_certs=cfg.verify_ssl_certs,
        max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )


def _create_openai_embeddings(cfg: EmbeddingConfig) -> Embeddings:
    return OpenAIEmbeddings(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model or "",
        dimensions=cfg.dim,
        chunk_size=cfg.batch_size,
        timeout=cfg.timeout,
    )


"""Машина состояний чата в функциональном стиле."""
CHAT_FACTORIES: dict[str, ICreateChat] = {
    Providers.OPENAI.value: _create_openai_compatible_chat,
    Providers.GIGACHAT.value: _create_gigachat_chat,
}

"""Машина состояний эмбеддингов в функциональном стиле."""
EMBEDDING_FACTORIES: dict[str, ICreateEmbeddings] = {
    Providers.OPENAI.value: _create_openai_embeddings,
}
