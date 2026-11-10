"""Настройка работы программы через конфигурационный файл."""

from pydantic import BaseModel, Field, SecretStr


class CompletionConfig(BaseModel):
    """Конфигурация модели генерации (LLM-чата)."""

    provider: str = Field(description="Провайдер LLM.")
    api_key: SecretStr = Field(repr=False, description="Ключ API для доступа к провайдеру.")

    verify_ssl_certs: bool = Field(default=False, description="Проверять ли SSL-сертификаты.")
    base_url: str = Field(default="", description="Путь API для OpenAI-провайдеров.")
    model: str = Field(default="", description="Название модели чата.")
    temperature: float = Field(default=0.1, description="Температура выборки токенов (0..1).")
    max_tokens: int = Field(default=10000, description="Максимальное число токенов в одном ответе модели.")
    timeout: int = Field(default=60, description="Время ожидания ответа от запроса к API, в секундах.")
    max_steps: int = Field(default=20, ge=1, description="Максимальное число шагов агента.")
    system_prompt: str = Field(default="You are a helpful assistant.", description="Системный промпт.")


class CollectionConfig(BaseModel):
    """Конфигурация одной коллекции документов для векторного поиска."""

    path: str = Field(description="Путь к папке с документами коллекции.")

    top_k: int = Field(default=5, ge=1, description="Сколько наиболее близких чанков возвращать.")
    chunk_size: int = Field(default=512, ge=1, description="Размер чанка (в символах).")
    chunk_overlap: int = Field(default=64, ge=0, description="Перекрытие чанков для сохранения контекста.")


class EmbeddingConfig(BaseModel):
    """Конфигурация модели эмбеддингов и векторного хранилища."""

    provider: str = Field(description="Провайдер эмбеддингов: 'openai' и совместимые.")

    api_key: SecretStr = Field(default="None", repr=False, description="Ключ API провайдера эмбеддингов.")
    collections: list[CollectionConfig] = Field(default_factory=list, description="Список путей к папкам.")
    verify_ssl_certs: bool = Field(default=False, description="Проверять ли SSL-сертификаты.")
    base_url: str = Field(default="", description="Путь API для OpenAI-провайдеров.")
    model: str = Field(default="", description="Название модели эмбеддингов.")
    dim: int = Field(default=1024, ge=1, description="Размерность вектора эмбеддинга.")
    db_path: str = Field(default="./rag.sqlite3", description="Путь к файлу векторной базы данных.")
    batch_size: int = Field(default=4, ge=1, description="Сколько документов обрабатывается за один запрос.")
    timeout: int = Field(default=60, description="Время ожидания ответа от запроса к API, в секундах.")
