"""LangGraph Server 用のエントリポイント。"""

from __future__ import annotations

import os
from typing import TypedDict, cast

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from .graph import DEFAULT_SYSTEM_PROMPT, build_state_graph
from .knowledge import KnowledgeBase
from .sandbox import DEFAULT_EXECUTION_POLICY, ExecutionPolicyName
from .state import DEFAULT_MODEL
from .tools import DEFAULT_TOOLS, make_search_tool

# プロセス内で共有する知識ベースのシングルトン。
_knowledge_base: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    """遅延生成の共有 KnowledgeBase を返す（埋め込みクライアントの生成を遅らせる）。"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base


def _default_model() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


def _execution_policy_from_env() -> ExecutionPolicyName:
    value = os.environ.get("GUARDED_AGENT_EXECUTION_POLICY", DEFAULT_EXECUTION_POLICY)
    if value not in ("host", "docker", "codex"):
        raise ValueError(
            "GUARDED_AGENT_EXECUTION_POLICY must be one of: host, docker, codex"
        )
    return cast(ExecutionPolicyName, value)


def make_graph():
    """サーバーがロードするコンパイル済みグラフを返すファクトリ。"""
    model = _default_model()
    tools = [*DEFAULT_TOOLS, make_search_tool(get_knowledge_base())]
    builder = build_state_graph(
        model,
        tools=tools,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        execution_policy=_execution_policy_from_env(),
    )
    return builder.compile()


class IngestState(TypedDict, total=False):
    """ingest グラフの状態。"""

    text: str
    source: str
    chunks: int


def _ingest(state: IngestState) -> IngestState:
    knowledge_base = get_knowledge_base()
    chunks = knowledge_base.add_text(
        state["text"],
        source=state.get("source") or "unknown",
    )
    return {"chunks": chunks}


def make_ingest_graph():
    """ドキュメント取り込み用グラフを返すファクトリ。"""
    builder = StateGraph(IngestState)
    builder.add_node("ingest", _ingest)
    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", END)
    return builder.compile()
