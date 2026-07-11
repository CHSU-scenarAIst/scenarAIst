from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_gigachat import GigaChat
from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    messages: list


# class State(TypedDict):
#     text: str
#     classification: str
#     entities: List[str]
#     summary: str


def chat_node(state: State) -> State:
    llm = GigaChat()
    response = llm.invoke(state["messages"])

    return {
        "messages": [
            *state["messages"],
            AIMessage(response.content),
        ]
    }


# Define tools
@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`.

    Args:
        a: First int
        b: Second int
    """
    return a * b * 2


def main():
    print("Hello from scenaraist!")

    load_dotenv()

    ### ЭТО И ЕСТЬ АГЕНТ!!!
    agent_builder = StateGraph(State)

    agent_builder.add_node("chat", chat_node)

    agent_builder.add_edge(START, "chat")
    agent_builder.add_edge("chat", END)

    agent = agent_builder.compile()
    ###

    history = []

    while True:
        text = input("> ")

        if text.lower() in {"exit", "quit"}:
            break

        history.append(HumanMessage(text))

        result = agent.invoke({"messages": history})

        history = result["messages"]

        print(history[-1].content)


if __name__ == "__main__":
    main()

# def classification_node(state: State):
#     ''' Classify the text into one of the categories: News, Blog, Research, or Other '''
#     prompt = PromptTemplate(
#         input_variables=["text"],
#         template="Classify the following text into one of the categories: News, Blog, Research, or Other.\n\nText:{text}\n\nCategory:"
#     )
#     message = HumanMessage(content=prompt.format(text=state["text"]))
#     classification = llm.invoke([message]).content.strip()
#     return {"classification": classification}


# def entity_extraction_node(state: State):
#     ''' Extract all the entities (Person, Organization, Location) from the text      '''
#     prompt = PromptTemplate(
#         input_variables=["text"],
#         template="Extract all the entities (Person, Organization, Location) from the following text. Provide the result as a comma-separated list.\n\nText:{text}\n\nEntities:"
#     )
#     message = HumanMessage(content=prompt.format(text=state["text"]))
#     entities = llm.invoke([message]).content.strip().split(", ")
#     return {"entities": entities}
