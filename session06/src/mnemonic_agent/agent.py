from __future__ import annotations

from typing import Any, Iterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from .graph import DEFAULT_SYSTEM_PROMPT, build_graph
from .state import DEFAULT_MODEL, Context, OpenAIModelName

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
    """短期記憶と長期記憶を搭載した AI エージェント。

    - 短期記憶: `session_id`（スレッド）ごとに会話履歴を checkpointer で保持する。
    - 長期記憶: `user_id` ごとに恒常的な事実を Store に抽出・検証して保存し、
      次のターン以降にセマンティック検索で参照する。
    """

    def __init__(
        self,
        model: BaseChatModel | None = None,
        *,
        tools=None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        call_model_name: OpenAIModelName = DEFAULT_MODEL,
    ) -> None:
        self.model = model or _default_model()
        self.call_model_name = call_model_name
        self.store = store or _default_store()
        self.graph = build_graph(
            self.model,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
            store=self.store,
        )

    def _config(self, session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def _context(
        self,
        user_id: str,
        *,
        model: OpenAIModelName | None = None,
    ) -> Context:
        return Context(user_id=user_id, model=model or self.call_model_name)

    def run(
        self,
        query: str,
        *,
        user_id: str = "default",
        session_id: str = "default",
        model: OpenAIModelName | None = None,
    ) -> str:
        """1 ターン実行し、アシスタントの最終回答テキストを返す。"""
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=query)]},
            config=self._config(session_id),
            context=self._context(user_id, model=model),
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
        model: OpenAIModelName | None = None,
    ) -> Iterator[Any]:
        """グラフの実行を逐次ストリームする（node ごとの更新を確認したいとき用）。"""
        yield from self.graph.stream(
            {"messages": [HumanMessage(content=query)]},
            config=self._config(session_id),
            context=self._context(user_id, model=model),
            stream_mode=stream_mode,
        )

    def recall(self, user_id: str = "default") -> list[str]:
        """指定ユーザーについて保存されている長期記憶を一覧する。"""
        items = self.store.search(("memories", user_id))
        return [item.value["text"] for item in items]
