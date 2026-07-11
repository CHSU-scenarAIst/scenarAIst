# О проекте

...

## Начало работы

```sh
cp .env.example .env
```

...

### Модели

```
GigaChat (owned_by=salutedevices)
GigaChat-2 (owned_by=salutedevices)
GigaChat-2-Max (owned_by=salutedevices)
GigaChat-2-Pro (owned_by=salutedevices)
GigaChat-Max (owned_by=salutedevices)
GigaChat-Max-preview (owned_by=salutedevices)
GigaChat-Plus (owned_by=salutedevices)
GigaChat-Pro (owned_by=salutedevices)
GigaChat-Pro-preview (owned_by=salutedevices)
GigaChat-preview (owned_by=salutedevices)
Embeddings (owned_by=salutedevices)
Embeddings-2 (owned_by=salutedevices)
EmbeddingsGigaR (owned_by=salutedevices)
GigaEmbeddings-3B-2025-09 (owned_by=salutedevices)
```

...

## Dev

### Установка

```sh
uv add langchain_gigachat python-dotenv langgraph langchain
uv init

uv python install 3.13
rm -rf .venv
uv venv --python 3.13
uv sync
```

...

```py
from dotenv import load_dotenv
from langchain_gigachat.chat_models import GigaChat

load_dotenv()

llm = GigaChat()

# список моделей
models = llm.get_models()
for model in models.data:
    print(f"{model.id_} (owned_by={model.owned_by})")
```

## Источники

[^1]: https://habr.com/ru/articles/891614/

[^2]: https://docs.langchain.com/oss/python/langgraph/quickstart
