"""构建并编译 LangGraph 多 Agent 状态图（途律 · TruLex）。"""

from functools import partial
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import NODES
from app.agents.state import AgentState


def _route_after_supervisor(state: AgentState) -> str:
    """supervisor -> 具体执行节点的条件路由。"""
    return state.get("route", "chat")


def build_agent(
    llm: Optional[Any] = None,
    tools: Optional[Any] = None,
    checkpointer: Optional[Any] = None,
    store: Optional[Any] = None,
):
    """构建七 Agent 状态图并 compile。

    :param llm: LLMProvider 实例
    :param tools: 工具函数字典
    :param checkpointer: LangGraph 短期记忆（PostgresSaver）
    :param store: LangGraph 长期记忆（PostgresStore）
    """
    builder = StateGraph(AgentState)

    supervisor = partial(NODES["supervisor"], llm=llm, tools=tools)
    waybill_reviewer = partial(NODES["waybill_reviewer"], llm=llm, tools=tools)
    statute_retrieval = partial(NODES["statute_retrieval"], llm=llm, tools=tools)
    case_retrieval = partial(NODES["case_retrieval"], llm=llm, tools=tools)
    liability_assessor = partial(NODES["liability_assessor"], llm=llm, tools=tools)
    document_writer = partial(NODES["document_writer"], llm=llm, tools=tools)
    compliance_guard = partial(NODES["compliance_guard"], llm=llm, tools=tools)

    builder.add_node("supervisor", supervisor)
    builder.add_node("waybill_reviewer", waybill_reviewer)
    builder.add_node("statute_retrieval", statute_retrieval)
    builder.add_node("case_retrieval", case_retrieval)
    builder.add_node("liability_assessor", liability_assessor)
    builder.add_node("document_writer", document_writer)
    builder.add_node("compliance_guard", compliance_guard)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "waybill": "waybill_reviewer",
            "statute": "statute_retrieval",
            "case": "case_retrieval",
            "liability": "liability_assessor",
            "document": "document_writer",
            "chat": "compliance_guard",
        },
    )
    for node in ("waybill_reviewer", "statute_retrieval", "case_retrieval",
                 "liability_assessor", "document_writer"):
        builder.add_edge(node, "compliance_guard")
    builder.add_edge("compliance_guard", END)

    return builder.compile(checkpointer=checkpointer, store=store)
