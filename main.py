# import os
from dotenv import load_dotenv
from langchain_gigachat.chat_models import GigaChat


def main():
    print("Hello from scenaraist!")

    load_dotenv()

    # gca = os.environ.get("GIGACHAT_CREDENTIALS")
    # gm = os.environ.get("GIGACHAT_MODEL")
    # gssl = os.environ.get("GIGACHAT_VERIFY_SSL_CERTS")

    llm = GigaChat(
        # credentials=gca,
        # model=gm,
        # scope="GIGACHAT_API_PERS",
        # verify_ssl_certs=gssl,
    )

    # # список моделей
    # models = llm.get_models()
    # for model in models.data:
    #     print(f"{model.id_} (owned_by={model.owned_by})")

    # простое одиночное сообщение
    msg = llm.invoke("Hello, GigaChat! Как меня зовут?")
    print(msg.content)

    # # потоковая выдача токенов?
    # for chunk in llm.stream("Напиши короткое стихотворение о программировании"):
    #     print(chunk.content, end="", flush=True)
    # print()


if __name__ == "__main__":
    main()
