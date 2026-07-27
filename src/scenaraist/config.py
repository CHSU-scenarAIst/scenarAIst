"""Конфигурация LLM."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ModelConfig:
    provider: str
    api_key: str
    model: str | None = None
    base_url: str | None = None
    verify_ssl_certs: bool = False


@dataclass(slots=True, frozen=True)
class CompletionConfig(ModelConfig):
    temperature: float = 0.8
    max_tokens: int = 4000
    system_prompt: str = "You are a helpful assistant."


@dataclass(slots=True, frozen=True)
class EmbeddingConfig(ModelConfig):
    dim: int = 1024
