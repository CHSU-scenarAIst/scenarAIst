pragma Singleton
import QtQuick

// ? NOTTODO перейти на базовые qm файлы с локализацией (самый распространённый подход)
QtObject {
    id: root

    property string language: "ru"

    property var translations: ({
            "Main.Title": {
                "en": "scenarAIst",
                "ru": "СценарИИст"
            },
            "Response.Title": {
                "en": "Model Responses",
                "ru": "Ответы LLM"
            },
            "Query.Count": {
                "en": "Queries",
                "ru": "Запросов"
            },
            "Query.Title": {
                "en": "User Queries",
                "ru": "Запросы пользователя"
            },
            "Clear.Btn": {
                "en": "Clear",
                "ru": "Очистить"
            },
            "Clear.Tip": {
                "en": "Clear LLM responses and user queries",
                "ru": "Очистить ответы LLM и запросы пользователя"
            },
            "Save.Response": {
                "en": "Save LLM response as JSON",
                "ru": "Сохранить ответ LLM в JSON"
            },
            "Load.Tasks": {
                "en": "Load tasks from file (1 task = 1 line)",
                "ru": "Загрузить задачи из файла (1 задача = 1 строка)"
            },
            "Exit.Question": {
                "en": "Are you sure you want to exit?",
                "ru": "Вы уверены, что хотите выйти?"
            },
            "Hotkeys.Send": {
                "en": "Send",
                "ru": "Отправить"
            },
            "Hotkeys.Insert": {
                "en": "Insert",
                "ru": "Вставить"
            },
            "Hotkeys.Mode": {
                "en": "Mode",
                "ru": "Режим"
            },
            "Hotkeys.Copy": {
                "en": "Copy",
                "ru": "Копировать"
            },
            "Hotkeys.Save": {
                "en": "Save as JSON...",
                "ru": "Сохранить как JSON..."
            },
            "Hotkeys.Scroll": {
                "en": "Scroll Response",
                "ru": "Прокрутка ответа"
            },
            "Hotkeys.New": {
                "en": "Add task",
                "ru": "Новая задача"
            },
            "Hotkeys.Delete": {
                "en": "Delete last task",
                "ru": "Удалить последнюю задачу"
            },
            "Hotkeys.Load": {
                "en": "Load tasks from file",
                "ru": "Загрузить задачи из файла"
            },
            "Hotkeys.Exit": {
                "en": "Exit",
                "ru": "Выход"
            },
            "Mode.CreateOne": {
                "en": "Question & Answer",
                "ru": "Вопрос–ответ"
            },
            "Mode.CreateSome": {
                "en": "Bulk creation",
                "ru": "Массовое создание"
            },
            "Mode.ChangeOne": {
                "en": "...",
                "ru": "Изменить один"
            },
            "Mode.ChangeSome": {
                "en": "...",
                "ru": "Массовое изменение"
            },
            "Query.Add.Text": {
                "en": "+",
                "ru": "+"
            },
            "Query.Add.Tip": {
                "en": "Add query",
                "ru": "Добавить запрос"
            },
            "Query.Delete.Tip": {
                "en": "Delete query",
                "ru": "Удалить запрос"
            },
            "Query.Send.Text": {
                "en": "▲ Send",
                "ru": "▲ Отправить"
            },
            "Query.Send.Tip": {
                "en": "Send query / run pipeline",
                "ru": "Отправить запрос / запустить конвейер"
            },
            "Query.Copy.Text": {
                "en": "⧉",
                "ru": "⧉"
            },
            "Query.Copy.Tip": {
                "en": "Copy LLM response",
                "ru": "Копировать ответ LLM"
            }
        })

    function tr(key) {
        const entry = translations[key];

        if (!entry) {
            console.warn("Missing translation:", key);
            return key;
        }

        return entry[language] || entry.en || key;
    }
}
