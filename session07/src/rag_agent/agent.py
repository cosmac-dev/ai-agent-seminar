from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from .graph import DEFAULT_SYSTEM_PROMPT, build_graph
from .knowledge import KnowledgeBase
from .state import Context
from .tools import DEFAULT_TOOLS, make_search_tool

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMS = 1536


def _default_model() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


def _default_store() -> BaseStore:
    """埋め込み index 付き Store を作る。失敗時は素の InMemoryStore にフォールバック。"""
    try:
        from langchain_openai import OpenAIEmbeddings

        return InMemoryStore(
            index={
                "embed": OpenAIEmbeddings(model=DEFAULT_EMBEDDING_MODEL),
                "dims": DEFAULT_EMBEDDING_DIMS,
                "fields": ["text"],
            }
        )
    except Exception:  # noqa: BLE001 - 埋め込みが使えない環境では素のStoreで動かす
        return InMemoryStore()


class Agent:
    """RAGツール、短期記憶、長期記憶を搭載した AI エージェント。

    - 短期記憶: `session_id`（スレッド）ごとに会話履歴を checkpointer で保持する。
    - 長期記憶: `user_id` ごとに恒常的な事実を Store に抽出・検証して保存し、
      次のターン以降にセマンティック検索で参照する。
    - RAGツール: `ingest()` で取り込んだドキュメント（知識ベース）から
      関連チャンクを検索し、回答の根拠として使う。
    """

    def __init__(
        self,
        model: BaseChatModel | None = None,
        *,
        tools=None,
        knowledge_base: KnowledgeBase | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
    ) -> None:
        self.model = model or _default_model()
        self.store = store or _default_store()
        self.knowledge_base = knowledge_base or KnowledgeBase()

        # ベースのツール群に、知識ベースへ束縛した RAG 検索ツールを加える
        base_tools = list(tools) if tools is not None else list(DEFAULT_TOOLS)
        base_tools.append(make_search_tool(self.knowledge_base))

        self.graph = build_graph(
            self.model,
            tools=base_tools,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
            store=self.store,
        )

    def ingest(self, text: str, *, source: str = "unknown") -> int:
        """ドキュメントを知識ベースへ取り込み、作成されたチャンク数を返す。

        チャンク化 → 埋め込み → 保存は決定的な前処理のため、
        LLM を介さず直接実行する。
        """
        return self.knowledge_base.add_text(text, source=source)

    def ingest_file(self, path: str | Path, *, source: str | None = None) -> int:
        """テキストファイルを知識ベースへ取り込み、作成されたチャンク数を返す。"""
        return self.knowledge_base.add_file(path, source=source)

    def _config(self, session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def run(
        self,
        query: str,
        *,
        user_id: str = "default",
        session_id: str = "default",
    ) -> str:
        """1 ターン実行し、アシスタントの最終回答テキストを返す。"""
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=query)]},
            config=self._config(session_id),
            context=Context(user_id=user_id),
        )
        for message in reversed(result["messages"]):
            if isinstance(message, AIMessage) and message.content:
                return str(message.content)
        return ""

    def stream(
        self,
        query: str,
        *,
        user_id: str = "default",
        session_id: str = "default",
        stream_mode: str = "updates",
    ) -> Iterator[Any]:
        """グラフの実行を逐次ストリームする（node ごとの更新を確認したいとき用）。"""
        yield from self.graph.stream(
            {"messages": [HumanMessage(content=query)]},
            config=self._config(session_id),
            context=Context(user_id=user_id),
            stream_mode=stream_mode,
        )

    def recall(self, user_id: str = "default") -> list[str]:
        """指定ユーザーについて保存されている長期記憶を一覧する。"""
        items = self.store.search(("memories", user_id))
        return [item.value["text"] for item in items]
