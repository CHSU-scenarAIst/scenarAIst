# scenarAIst

...

## Getting Started

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Python 3.14+
- GigaChat API credentials ([obtain here](https://developers.sber.ru/gigachat))

### Installation

```sh
# Clone the repository
git clone https://github.com/example/scenaraist.git
cd scenaraist

rm -rf ./.venv/
uv venv --python 3.14
uv sync

# Copy and configure environment variables
cp .env.example .env
```

### Usage

```sh
scenaraist
uv run scenaraist
python -m scenaraist
```

## Development

### Environment Setup

```sh
# Install development dependencies
uv sync --dev
```

### Development Commands

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

## Available Models

| Model                | Owner         |
| -------------------- | ------------- |
| GigaChat             | salutedevices |
| GigaChat-2           | salutedevices |
| GigaChat-2-Max       | salutedevices |
| GigaChat-2-Pro       | salutedevices |
| GigaChat-Max         | salutedevices |
| GigaChat-Max-preview | salutedevices |
| GigaChat-Plus        | salutedevices |
| GigaChat-Pro         | salutedevices |
| GigaChat-Pro-preview | salutedevices |
| GigaChat-preview     | salutedevices |

## Resources

- [Habr article: Building AI agents with LangChain](https://habr.com/ru/articles/891614/)
- [LangGraph Quickstart Guide](https://docs.langchain.com/oss/python/langgraph/quickstart)
- [GigaChat Developer Portal](https://developers.sber.ru/gigachat)
- https://python.langchain.com/docs/
- https://langchain-ai.github.io/langgraph/
