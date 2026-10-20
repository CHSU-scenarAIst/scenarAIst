pragma Singleton
import QtQuick

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
            "Response.Count": {
                "en": "Responses",
                "ru": "Ответы"
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
            "Mode.QuestionAnswer": {
                "en": "Question & Answer",
                "ru": "Вопрос–ответ"
            },
            "Mode.ConveyorCreate": {
                "en": "Bulk creation",
                "ru": "Массовое создание"
            },
            "Mode.ConveyorCheck": {
                "en": "Bulk check & edit",
                "ru": "Массовая проверка и редактирование"
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
            // TODO Exit from app
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
