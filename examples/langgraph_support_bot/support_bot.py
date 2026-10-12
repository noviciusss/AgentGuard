"""A deliberately unsafe support bot used by the README scan example.

The file is parsed by AgentGuard and is not executed as part of the example.
"""

from langgraph.graph import END, START, StateGraph
from openai import OpenAI
from typing_extensions import TypedDict


class SupportState(TypedDict):
    messages: list[str]


client = OpenAI()


def answer_customer(state: SupportState) -> SupportState:
    while True:
        try:
            response = client.responses.create(
                model="gpt-support",
                input=state["messages"],
            )
            return {"messages": [str(response)]}
        except OSError:
            continue


def search_orders(state: SupportState) -> SupportState:
    return {"messages": ["order lookup"]}


def search_policies(state: SupportState) -> SupportState:
    return {"messages": ["policy lookup"]}


def build_graph() -> object:
    builder = StateGraph(SupportState)
    builder.add_node("answer_customer", answer_customer)
    builder.add_node("search_orders", search_orders)
    builder.add_node("search_policies", search_policies)
    builder.add_edge(START, "search_orders")
    builder.add_edge(START, "search_policies")
    builder.add_edge("search_orders", END)
    builder.add_edge("search_policies", END)
    return builder.compile()
