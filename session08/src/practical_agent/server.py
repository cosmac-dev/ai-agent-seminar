"""LangGraph Server 用のエントリポイント。

`langgraph.json` がこのモジュールの `make_graph` を参照する。
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
from .state import DEFAULT_MODEL
from .tools import DEFAULT_TOOLS, make_search_tool

# プロセス内で共有する知識ベースのシングルトン。
# エージェントグラフの検索ツールと ingest グラフの両方がこれを参照する。
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


def make_graph():
    """サーバーがロードするコンパイル済みグラフを返すファクトリ。

    checkpointer / store は渡さない。サーバーが自動で注入する。
    共有 KnowledgeBase に束縛した RAG 検索ツールを既定ツールに加える。
    """
    model = _default_model()
    tools = [*DEFAULT_TOOLS, make_search_tool(get_knowledge_base())]
    builder = build_state_graph(model, tools=tools, system_prompt=DEFAULT_SYSTEM_PROMPT)
    return builder.compile()


class IngestState(TypedDict, total=False):
    """ingest グラフの状態。

    - text: 取り込むドキュメント本文（入力）。
    - source: 出典ラベル（入力・任意）。
    - chunks: 作成されたチャンク数（出力）。
    """

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
    """ドキュメント取り込み用グラフを返すファクトリ。

    LLM を使わない決定的なパイプライン（チャンク化 → 埋め込み → 保存）を
    1 ノードのグラフとして公開する。共有 KnowledgeBase に書き込むため、
    取り込んだ内容はエージェントグラフの検索ツールから参照できる。
    """
    builder = StateGraph(IngestState)
    builder.add_node("ingest", _ingest)
    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", END)
    return builder.compile()
