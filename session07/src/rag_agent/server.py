"""LangGraph Server 用のエントリポイント。

`langgraph.json` がこのモジュールの `make_graph` / `make_ingest_graph` を参照する。
サーバー環境では checkpointer / store はサーバーが所有・注入するため、
ここでは **永続化を渡さずに** コンパイルする（渡しても無視される）。

長期記憶のセマンティック検索設定（埋め込みモデル・次元・対象フィールド）は
`langgraph.json` の `store.index` で宣言する。

RAG の知識ベース（`KnowledgeBase`）はこのモジュールのプロセス内シングルトンで、
エージェントグラフ（検索）と取り込みグラフ（ingest）が同じインスタンスを共有する。
サーバーには実行中プロセスの Python API を直接呼ぶ手段が無いため、
ドキュメントの取り込み口として専用の `ingest` グラフを公開する。
取り込み自体は LLM を使わない決定的なパイプライン
（チャンク化 → 埋め込み → 保存）であり、グラフは `KnowledgeBase` の薄いラッパに留める。
"""

from __future__ import annotations

from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from .graph import DEFAULT_SYSTEM_PROMPT, build_state_graph
from .knowledge import KnowledgeBase
from .tools import DEFAULT_TOOLS, make_search_tool

DEFAULT_MODEL = "gpt-4o-mini"

_knowledge_base: KnowledgeBase | None = None


def _default_model() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


def get_knowledge_base() -> KnowledgeBase:
    """エージェントグラフと取り込みグラフが共有する知識ベースを返す。"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base


def make_graph():
    """サーバーがロードするエージェントグラフを返すファクトリ。

    checkpointer / store は渡さない。サーバーが自動で注入する。
    """
    model = _default_model()
    tools = [*DEFAULT_TOOLS, make_search_tool(get_knowledge_base())]
    builder = build_state_graph(
        model,
        tools=tools,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    )
    return builder.compile()


class IngestInput(TypedDict):
    """取り込みグラフへの入力。"""

    text: str
    source: str


class IngestState(TypedDict):
    """取り込みグラフの状態。"""

    text: str
    source: str
    chunks_added: int


def _ingest(state: IngestState) -> IngestState:
    """ドキュメントを知識ベースへ取り込む node（LLMは使わない）。"""
    count = get_knowledge_base().add_text(
        state["text"],
        source=state.get("source") or "api",
    )
    return {"chunks_added": count}


def make_ingest_graph():
    """ドキュメント取り込み用グラフを返すファクトリ。

    API 経由（POST /runs/wait, assistant_id="ingest"）で
    `{"text": "...", "source": "..."}` を渡すと知識ベースへ取り込まれる。
    """
    builder = StateGraph(IngestState, input_schema=IngestInput)
    builder.add_node("ingest", _ingest)
    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", END)
    return builder.compile()
