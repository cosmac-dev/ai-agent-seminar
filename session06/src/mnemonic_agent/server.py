"""LangGraph Server 用のエントリポイント。

`langgraph.json` がこのモジュールの `make_graph` を参照する。
サーバー環境では checkpointer / store はサーバーが所有・注入するため、
ここでは **永続化を渡さずに** コンパイルする（渡しても無視される）。

長期記憶のセマンティック検索設定（埋め込みモデル・次元・対象フィールド）は
`langgraph.json` の `store.index` で宣言する。
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .graph import DEFAULT_SYSTEM_PROMPT, build_state_graph
from .state import DEFAULT_MODEL


def _default_model() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


def make_graph():
    """サーバーがロードするコンパイル済みグラフを返すファクトリ。

    checkpointer / store は渡さない。サーバーが自動で注入する。
    """
    model = _default_model()
    builder = build_state_graph(model, system_prompt=DEFAULT_SYSTEM_PROMPT)
    return builder.compile()
