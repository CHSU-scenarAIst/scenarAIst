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
> Показатель эффективности: 91% точности после четвёртой перегенерации (Сценарий на 100 действий).

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
# Установить `uv`
## wget
wget -qO- https://astral.sh/uv/install.sh | sh
## curl
curl -LsSf https://astral.sh/uv/install.sh | sh
## windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
###

git clone https://github.com/CHSU-scenarAIst/scenarAIst && cd scenaraist
uv sync

scenaraist      # Запуск с логированием
uv run -m src   # Запуск без логирования
```

## Модели

- GigaChat: [Studio - Личный кабинет технологических продуктов Сбера](https://developers.sber.ru/studio/workspaces/)
- Z.ai: `https://docs.z.ai/guides/overview/pricing#other-pricing`
- OpenRouter: API не работает в РФ
- DeepSeek Open Platform: требует деньги
- OfoxAI: нет бесплатных вариантов
- ProxyAPI: РФ, требует деньги
- AITunnel: РФ, требует деньги
- RouterAI: РФ, требует деньги
- SambaNova Cloud: не работает в РФ с VPN
- `https://www.orcarouter.ai/`
- `https://teamorouter.com/`
- `https://agentrouter.org/`
- `https://tokenharbor.ai/`
- `https://router.bynara.id/`
- `https://freerouter.eu.cc/`
- BotHub,
- KodikRouter,

## Литература

- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangChain](https://docs.langchain.com/oss/python/langchain/overview)
- [sqlite-vec](https://alexgarcia.xyz/sqlite-vec/python.html)
- [LangChain - Tavily Docs](https://docs.tavily.com/documentation/integrations/langchain)
- [Tavily API Platform](https://app.tavily.com/home)

## Dev

```sh
uv sync --dev   # Install development dependencies
```

### Команды

| Command                                        | Description                           |
| ---------------------------------------------- | ------------------------------------- |
| `pytest`                                       | Run tests with coverage               |
| `ruff check --fix`                             | Lint the codebase                     |
| `ruff format`                                  | Format the codebase                   |
| `mypy`                                         | Type-check the codebase               |
| `uv run pre-commit install`                    | ...                                   |
| `uv run pre-commit autoupdate`                 | ...                                   |
| `uv run  pre-commit validate-config`           | pre-commit                            |
| `uv run  pre-commit run --all-files --verbose` | запуск принудительно по всему проекту |

### .qmlformat.ini

TODO - нужен ли он мне?

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

Придумать документацию к вымышленным приборам, провести тесты:

- [ ] Создание метрики точности
- [ ] Прогон агента-Сценариста на инструкциях 5 типов оборудования
- [ ] Сравнение ответов по структуре/смыслу и расчёт метрики точности
- [ ] Может ли LLM написать длинный Сценарий без инструментов?
- [ ] Может ли LLM написать длинный Сценарий с помощью инструментов?
- [ ] Сценарий на предмет 6 должен быть написан на основе предметов 1..5, просто заменив номера и/или что-то дополнив, но не с нуля
- [ ] Подача эталонных Сценариев 1..5 в контекст (через RAG-коллекцию)
- [ ] Сравнение структуры Сценария 6 с эталонами
