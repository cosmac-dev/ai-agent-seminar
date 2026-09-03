"""LangGraph Server 用のエントリポイント。"""

from __future__ import annotations

import os
from typing import TypedDict, cast

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from .graph import build_state_graph
from .knowledge import KnowledgeBase
from .sandbox import DEFAULT_EXECUTION_POLICY, ExecutionPolicyName
from .state import DEFAULT_MODEL
from .tools import DEFAULT_TOOLS, make_search_tool

_knowledge_base: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base


def _default_model() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


def _execution_policy_from_env() -> ExecutionPolicyName:
    value = os.environ.get(
        "PLANNING_AGENT_EXECUTION_POLICY",
        DEFAULT_EXECUTION_POLICY,
    )
    if value not in ("host", "docker", "codex"):
        raise ValueError(
            "PLANNING_AGENT_EXECUTION_POLICY must be one of: host, docker, codex"
        )
    return cast(ExecutionPolicyName, value)


def make_graph():
    """サーバーがロードする Planning Agent グラフを返す。"""
    model = _default_model()
    tools = [*DEFAULT_TOOLS, make_search_tool(get_knowledge_base())]
    return build_state_graph(
        model,
        tools=tools,
        execution_policy=_execution_policy_from_env(),
    ).compile()


class IngestState(TypedDict, total=False):
    text: str
    source: str
    chunks: int


def _ingest(state: IngestState) -> IngestState:
    chunks = get_knowledge_base().add_text(
        state["text"],
        source=state.get("source") or "unknown",
    )
    return {"chunks": chunks}


def make_ingest_graph():
    builder = StateGraph(IngestState)
    builder.add_node("ingest", _ingest)
    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", END)
    return builder.compile()
