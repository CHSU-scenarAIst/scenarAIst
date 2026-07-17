# scenarAIst

...

## Начало

### Подготовка

- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Скачивание

```sh
# Clone the repository
git clone https://github.com/example/scenaraist.git
cd scenaraist

uv venv --python 3.14
uv python pin 3.14
uv sync

# Copy and configure environment variables
cp .env.example .env

curl https://openrouter.ai/api/v1/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

### Использование

```sh
# без логирования
scenaraist
uv run scenaraist

# с логированием
python -m scenaraist
uv run -m scenaraist
```

## Для разработчиков

### Установка зависимостей

```sh
# Install development dependencies
uv sync --dev
```

### Команды

| Command                   | Description             |
| ------------------------- | ----------------------- |
| `uv run pytest`           | Run tests with coverage |
| `uv run ruff check --fix` | Lint the codebase       |
| `uv run ruff format`      | Format the codebase     |
| `uv run mypy`             | Type-check the codebase |

### Pre-commit Hooks

To set up pre-commit hooks for automated code quality checks:

```sh
uv run pre-commit install
pre-commit autoupdate
```

## Модели

BotHub, KodikRouter,

- ProxyAPI: РФ, требует деньги
- AITunnel: РФ, требует деньги
- OfoxAI: [OK](https://ofox.ai/ru/models/z-ai/glm-4.7-flash%3Afree)
- RouterAI: РФ, требует деньги
- OpenRouter: API не работает в РФ
- SambaNova Cloud: не работает в РФ с VPN
- DeepSeek Open Platform: требует деньги
- ...

| GigaChat Model | Owner         |
| -------------- | ------------- |
| GigaChat-2     | salutedevices |
| GigaChat-2-Max | salutedevices |
| GigaChat-2-Pro | salutedevices |

## Литературы

- [Studio - Личный кабинет технологических продуктов Сбера](https://developers.sber.ru/studio/workspaces/)
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangChain](https://docs.langchain.com/oss/python/langchain/overview)
- [Полное руководство (с кодом) AI агента с использованием LangGraph](https://habr.com/ru/articles/891614/)
- [Создание умных AI-агентов: полный курс по LangGraph от А до Я. Часть 3.](https://habr.com/ru/companies/amvera/articles/949376/)
- [sqlite-vec](https://alexgarcia.xyz/sqlite-vec/python.html)
- [LangChain - Tavily Docs](https://docs.tavily.com/documentation/integrations/langchain)
- [Tavily API Platform](https://app.tavily.com/home)
