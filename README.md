# scenarAIst

- Актуальность: Генеративный языковой ИИ на один и тот же запрос даёт разные ответы. Важно не столько содержание, сколько структура и формат ответа, отправная точка, раскрытие важных понятий и то, как этот ответ завершился.
- Проблема: ИИ не подходит для задач, требующих детерминированного механизма решения.
- Объект: генеративный языковой ИИ.
- Предмет: Схожесть ответа по структуре и смысловой нагрузке.
- Цель: Структурирование ответа и схожесть по смысловой нагрузке.
- Гипотеза: Можно достичь 91% схожести ответов от одной и той же модели при одном и том же запросе.
- Методы: Наблюдение, эксперименты.

## Описание решения

> Сценарий - инструкция использования устройства, состоящая из атомарных операций.
> ИИ-сценарист - в регламенте описание устройства, технологические карты. Есть примеры готовых Сценариев. Надо создать новый. Скрытые смыслы модель должна понять сама.

Пример:

- Включение утюга У-505 (Сценарий)
  - Проверить, что вилка есть (0 - правильно, на своём месте, но не обязательно)
  - Взять вилку А-101 (1 - операция шага правильная, но объект требует корректировки)
  - Попить чай (2 - правильно, но не своём месте: должно быть в конце)
  - Воткнуть в розетку B-202 (4 - правильно и на своём месте)
  - ...
  - Покричать на небо (3 - неправильно)
  - Нажать на кнопку C-304 для включения

## Использовать

```sh
### install `uv`
wget -qO- https://astral.sh/uv/install.sh | sh
curl -LsSf https://astral.sh/uv/install.sh | sh
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
###

git clone https://github.com/example/scenaraist.git
cd scenaraist
uv sync

scenaraist      # Запуск с логированием
uv run -m src   # Запуск без логирования
```

## Модели

BotHub, KodikRouter,

- OfoxAI: [OK](https://ofox.ai/ru/models/z-ai/glm-4.7-flash%3Afree)
- ProxyAPI: РФ, требует деньги
- AITunnel: РФ, требует деньги
- DeepSeek Open Platform: требует деньги
- RouterAI: РФ, требует деньги
- OpenRouter: API не работает в РФ
- SambaNova Cloud: не работает в РФ с VPN
- `https://www.orcarouter.ai/`
- `https://teamorouter.com/`
- `https://agentrouter.org/`
- `https://tokenharbor.ai/`
- `https://router.bynara.id/`
- `https://freerouter.eu.cc/`

| GigaChat Model | Owner         |
| -------------- | ------------- |
| GigaChat-2     | salutedevices |
| GigaChat-2-Max | salutedevices |
| GigaChat-2-Pro | salutedevices |
| ...            | ...           |

## Литература

- [Studio - Личный кабинет технологических продуктов Сбера](https://developers.sber.ru/studio/workspaces/)
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangChain](https://docs.langchain.com/oss/python/langchain/overview)
- [Полное руководство (с кодом) AI агента с использованием LangGraph](https://habr.com/ru/articles/891614/)
- [Создание умных AI-агентов: полный курс по LangGraph от А до Я. Часть 3.](https://habr.com/ru/companies/amvera/articles/949376/)
- [sqlite-vec](https://alexgarcia.xyz/sqlite-vec/python.html)
- [LangChain - Tavily Docs](https://docs.tavily.com/documentation/integrations/langchain)
- [Tavily API Platform](https://app.tavily.com/home)

## Dev

```sh
uv sync --dev   # Install development dependencies
```

### Команды

| Command            | Description             |
| ------------------ | ----------------------- |
| `pytest`           | Run tests with coverage |
| `ruff check --fix` | Lint the codebase       |
| `ruff format`      | Format the codebase     |
| `mypy`             | Type-check the codebase |

### Pre-commit Hooks

To set up pre-commit hooks for automated code quality checks:

```sh
uv run pre-commit install
pre-commit autoupdate
```

### .qmlformat.ini

```ini
[General]
FunctionsSpacing=false
IndentWidth=4
MaxColumnWidth=100
NewlineType=native
NormalizeOrder=false
ObjectsSpacing=false
SemicolonRule=always
SortImports=false
UseTabs=false
```

### Генерация датасета

Нужен датасет на тему "Новый функциональный язык программирования 'ЖёПка'". Датасет - подробная документация к этому языку для разработчиков.

Ключевые особенности языка:

- код пишется на русском языке
- в языке нет скобок и отступов - вместо них новый уровень вложенности кода делается с помощью "3"
- названия операторов - буквально перевод с Python
- каждый файл начинается с "жёпка принадлежит <имя_файла.ж>", то есть буквально импорт файла в самого себя, без чего программа не запустится

Документация должна быть на двух языках: русском и английском, причём:

- на русском языке будет ТОЛЬКО описание языка, операторов и всех правил грамматики
- на английском языке будут ТОЛЬКО примеры кода типа "Привет, мир!", "перебор цикла", "поиск факториала" и тд, то есть код пишется на русском, но комментарии к нему - на английском.

Документация должна быть вперемешку в форматах: JSON, HTML, TXT, CSV, MD, PDF, DOCX, EXCEL. Если что-то написано в одном файле, то эта информация не должна повторяться в других файлах, но может быть ссылка/упоминание, что эта инфомация находится в другом файле.

Собери итоговый результат в архив и отправь в чат.
