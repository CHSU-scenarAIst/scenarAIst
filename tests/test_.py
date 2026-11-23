"""Тесты соответствия работы программы требованиям из ТЗ"""

import json
import logging
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import ValidationError

from src.agent.model import Providers
from src.agent.schema import (
    AgentResponse,
    AgentState,
    Scenario,
    SerializedResponse,
    Step,
)
from src.agent.tools import (
    DeleteStepSchema,
    InsertStepSchema,
    UpdateStepSchema,
    delete_step,
    insert_step,
    update_step,
)
from src.agent.vec_db import ALLOWED_EXTS, CollectionConfig, VectoreStoreBuilder
from src.ui.handler import HandlerBackend, InvokeAgent

LOGGER = logging.getLogger(__name__)


# * Вспомогательные функции.


def check(condition: bool, message: str) -> None:
    """Проверка условия вместо `assert` (шаблон Arrange-Act-Assert)."""
    if not condition:
        raise AssertionError(message)


def make_steps(count: int) -> list[Step[str]]:
    """Создать список Шагов с идентификаторами s1..sN."""
    return [
        Step[str](id=f"s{i}", actor=f"Персонал-{i}", target=f"Объект-{i}", action="USE")
        for i in range(1, count + 1)
    ]


def make_tool_runtime(steps: list[Step[str]]) -> ToolRuntime[None, AgentState]:
    """Подменить ToolRuntime для прямого вызова инструментов агента."""
    state = AgentState(response=AgentResponse(scenario=Scenario(steps=steps)))
    return cast(
        "ToolRuntime[None, AgentState]",
        SimpleNamespace(state=state, tool_call_id="test-call-id"),
    )


def get_update(result: Command[Any]) -> dict[str, Any]:
    """Получить словарь обновлений состояния из результата инструмента."""
    update = result.update
    if update is None:
        raise AssertionError("Инструмент не вернул обновление состояния.")
    if not isinstance(update, dict):
        raise TypeError(f"Обновление состояния не словарь: {type(update)}.")
    return update


def make_handler() -> HandlerBackend:
    """Создать обработчик сигналов UI с каталогом ответов во временном каталоге."""

    class TestInvoke(InvokeAgent):
        def invoke(self, task: str, min_steps: int, add_instruct: str) -> str:
            return f"Вызов агента с параметрами: {task}, {min_steps}, {add_instruct}"

    invoker = TestInvoke()
    return HandlerBackend(invoker=invoker, write_response=False)


# * Требования к функциональным характеристикам.


def test_response_format() -> None:
    """[Результаты представляются в формате] "steps" с атрибутами order/actor/target/action."""
    check_response_format = 3
    response = AgentResponse(scenario=Scenario(steps=make_steps(check_response_format)))
    raw = response.serialize()
    data = json.loads(raw)
    check("steps" in data, "В ответе отсутствует ключ 'steps'.")
    check(
        len(data["steps"]) == check_response_format,
        "Число Шагов в ответе не совпадает с исходным.",
    )
    first = data["steps"][0]
    for attr in ("order", "actor", "target", "action"):
        check(attr in first, f"В Шаге отсутствует атрибут '{attr}'.")
    check(
        [s["order"] for s in data["steps"]] == [1, 2, 3],
        "Порядковые номера Шагов неверны.",
    )


def test_scenario_extension() -> None:
    """[Поддержка «продолжения сценария»]: добавление Шагов к текущему Сценарию (insert_step)."""
    rtm = make_tool_runtime(make_steps(2))
    new_step = Step[str](id="new", actor="Новый", target="Объект", action="TAKE")
    result = insert_step(rtm, [InsertStepSchema(step_after_id=None, step=new_step)])
    ids = [s.id for s in get_update(result)["response"].steps]
    check(ids == ["s1", "s2", "new"], f"Шаг не добавлен в конец Сценария: {ids}.")


def test_scenario_regeneration() -> None:
    """[Поддержка «перегенерации»]: замену выбранных Шагов (update_step)."""
    rtm = make_tool_runtime(make_steps(2))
    replacement = Step[str](actor="Обновлённый", target="Объект", action="TAKE")
    result = update_step(rtm, [UpdateStepSchema(id="s1", new_step=replacement)])
    replaced = get_update(result)["response"].steps[0]
    check(replaced.id == "s1", "Шаг 's1' не заменён.")
    check(replaced.actor == "Обновлённый", "Атрибуты Шага не обновлены.")


def test_scenario_regeneration_replaces_only_selected_step() -> None:
    """[Перегенерация заменяет только выбранные Шаги]: остальные сохраняются."""
    rtm = make_tool_runtime(make_steps(3))
    replacement = Step[str](actor="Обновлённый", target="Объект", action="TAKE")
    result = update_step(rtm, [UpdateStepSchema(id="s2", new_step=replacement)])
    ids = [s.id for s in get_update(result)["response"].steps]
    check(ids == ["s1", "s2", "s3"], f"Состав Сценария изменён некорректно: {ids}.")


def test_delete_step() -> None:
    """[Изменение существующего сценария]: удаление Шагов по их идентификаторам (delete_step)."""
    rtm = make_tool_runtime(make_steps(3))
    result = delete_step(rtm, [DeleteStepSchema(id="s2")])
    ids = [s.id for s in get_update(result)["response"].steps]
    check(ids == ["s1", "s3"], f"Шаг 's2' не удалён: {ids}.")


def test_delete_step_missing_id_canceled() -> None:
    """[Надёжность] - обработка ошибок: удаление несуществующего Шага отменяется."""
    rtm = make_tool_runtime(make_steps(2))
    result = delete_step(rtm, [DeleteStepSchema(id="missing")])
    update = get_update(result)
    check("response" not in update, "Сценарий изменён при несуществующем id.")
    check(
        "Canceled" in update["messages"][0].content,
        "Об ошибке не сообщено в сообщении инструмента.",
    )


def test_insert_step_missing_after_id_canceled() -> None:
    """[Надёжность] - обработка ошибок: вставка после несуществующего Шага отменяется."""
    rtm = make_tool_runtime(make_steps(2))
    result = insert_step(
        rtm,
        [
            InsertStepSchema(
                step_after_id="missing",
                step=Step[str](actor="a", target="t", action="USE"),
            )
        ],
    )
    update = get_update(result)
    check("response" not in update, "Сценарий изменён при несуществующем step_after_id.")
    check(
        "Canceled" in update["messages"][0].content,
        "Об ошибке не сообщено в сообщении инструмента.",
    )


def test_step_validation_missing_attributes() -> None:
    """[Формирование сценария по внутренней схеме данных] - Шаг без обязательных полей отвергается."""
    try:
        Step[str](actor="a")  # type: ignore[call-arg]
    except ValidationError:
        return
    raise AssertionError("Шаг без обязательных атрибутов target/action создан.")


def test_unique_step_ids() -> None:
    """Каждый Шаг получает уникальный идентификатор."""
    check_unique_step_id = 100
    steps = make_steps(check_unique_step_id)
    ids = {s.id for s in steps}
    check(len(ids) == check_unique_step_id, "Идентификаторы Шагов не уникальны.")


def test_duplicate_step_ids_keep_first_index() -> None:
    """[Надёжность]: дубликат id Шага не искажает индекс первого вхождения."""
    steps = make_steps(3)
    steps[2].id = "s1"  # дубликат id первого Шага
    response = AgentResponse(scenario=Scenario(steps=steps))
    check(
        response.find("s1") == 0,
        "При дубликате id индекс первого вхождения потерян.",
    )
    check(
        response.steps[0].id == "s1" and response.steps[2].id == "s1",
        "Шаги с дубликатом id изменены при индексации.",
    )


def test_folder_hash_detects_content_change() -> None:
    """[Переиндексирование векторного хранилища]: хеш папки изменяется при изменении содержимого файлов."""
    builder = VectoreStoreBuilder(db_path=":memory:")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "doc.txt").write_text("исходный текст", encoding="utf-8")
        hash_before = builder._calculate_hash(folder)
        (folder / "doc.txt").write_text("новый текст!!", encoding="utf-8")
        stat = (folder / "doc.txt").stat()
        os.utime(folder / "doc.txt", ns=(stat.st_atime_ns, stat.st_mtime_ns))
        check(
            builder._calculate_hash(folder) != hash_before,
            "Хеш папки не изменился при изменении содержимого файла.",
        )


def test_scenario_roundtrip_serialization() -> None:
    """[Изменение существующего сценария] - Сценарий передаётся агенту как back_request."""
    check_serialization = 2
    response = AgentResponse(
        query="запрос",
        answer="ответ",
        scenario=Scenario(steps=make_steps(check_serialization)),
    )
    raw = response.serialize()
    state = AgentState.from_back_request(raw, "дополнить сценарий")
    check(
        state.response.count_steps() == check_serialization,
        "Число Шагов после разбора back_request неверное.",
    )
    check(
        state.response.query == "дополнить сценарий",
        "Инструкция не сохранена как запрос.",
    )
    check(
        state.response.steps[0].actor == "Персонал-1",
        "Атрибуты Шагов не восстановлены.",
    )


def test_connectable_source_formats() -> None:
    """[Управление данными файлового хранилища]: индексация текстовых документов и файлов сценариев."""
    required_formats = {".pdf", ".txt", ".docx", ".md", ".csv", ".xls", ".xlsx"}
    check(
        required_formats <= ALLOWED_EXTS,
        f"Поддерживаемые форматы источников неполные: {sorted(ALLOWED_EXTS)}.",
    )


def test_context_search_accuracy_configurable() -> None:
    """[Управление данными файлового хранилища]: настройка точности поиска контекста (top_k коллекции)."""
    check_context_search = 3
    collection = CollectionConfig(path=Path("./docs"), top_k=3)
    check(
        collection.top_k == check_context_search,
        "Точность поиска контекста (top_k) не настраивается конфигурацией коллекции.",
    )


def test_llm_provider_validation() -> None:
    """[Поддержка провайдеров LLM-агентов - OpenAI, GigaChat]: неизвестный провайдер отвергается."""
    check(
        {p.value for p in Providers} == {"openai", "gigachat"},
        f"Набор провайдеров неверен: {Providers}.",
    )


def test_unknown_provider_rejected() -> None:
    """[Надёжность] - обработка ошибок: конфигурация с неизвестным провайдером отвергается схемой."""
    try:
        Providers("unknown")
    except ValueError:
        return
    except Exception as e:
        raise AssertionError(f"Неожиданная ошибка при неизвестном провайдере: {e}") from e
    raise AssertionError("Неизвестный провайдер LLM не отвергнут.")


def test_contract_fields() -> None:
    """[Упаковка ответа во входной формат тренажёра]: контракт обмена данными по API."""
    raw = AgentResponse(scenario=Scenario(steps=make_steps(1))).serialize()
    data = json.loads(raw)
    contract = SerializedResponse.model_validate(data)
    check(contract.steps[0].order == 1, "Контракт API не содержит поле 'order'.")
    check({"query", "answer", "sources", "steps"} <= set(data), "Контракт API неполный.")
