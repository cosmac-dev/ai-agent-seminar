from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from .graph import DEFAULT_SYSTEM_PROMPT, build_graph
from .knowledge import KnowledgeBase
from .sandbox import DEFAULT_EXECUTION_POLICY, ExecutionPolicyName
from .state import DEFAULT_MODEL, Context, OpenAIModelName
from .tools import DEFAULT_TOOLS, make_search_tool

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
    """HITL とサンドボックス付きの実務エージェント。"""

    def __init__(
        self,
        model: BaseChatModel | None = None,
        *,
        tools=None,
        knowledge_base: KnowledgeBase | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        execution_policy: ExecutionPolicyName = DEFAULT_EXECUTION_POLICY,
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        call_model_name: OpenAIModelName = DEFAULT_MODEL,
    ) -> None:
        self.model = model or _default_model()
        self.call_model_name = call_model_name
        self.execution_policy = execution_policy
        self.store = store or _default_store()
        self.knowledge_base = knowledge_base or KnowledgeBase()

        base_tools = list(tools) if tools is not None else list(DEFAULT_TOOLS)
        base_tools.append(make_search_tool(self.knowledge_base))

        self.graph = build_graph(
            self.model,
            tools=base_tools,
            system_prompt=system_prompt,
            execution_policy=execution_policy,
            checkpointer=checkpointer,
            store=self.store,
        )

    def ingest(self, text: str, *, source: str = "unknown") -> int:
        """ドキュメントを知識ベースへ取り込み、作成されたチャンク数を返す。"""
        return self.knowledge_base.add_text(text, source=source)

    def ingest_file(self, path: str | Path, *, source: str | None = None) -> int:
        """テキストファイルを知識ベースへ取り込み、作成されたチャンク数を返す。"""
        return self.knowledge_base.add_file(path, source=source)

    def _config(self, session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def _context(
        self,
        user_id: str,
        *,
        model: OpenAIModelName | None = None,
    ) -> Context:
        return Context(user_id=user_id, model=model or self.call_model_name)

    def invoke(
        self,
        query: str | dict[str, Any] | Command,
        *,
        user_id: str = "default",
        session_id: str = "default",
        model: OpenAIModelName | None = None,
    ) -> dict[str, Any]:
        """グラフを実行し、`__interrupt__` を含む生の state を返す。"""
        if isinstance(query, str):
            input_value: dict[str, Any] | Command = {
                "messages": [HumanMessage(content=query)]
            }
        else:
            input_value = query

        return self.graph.invoke(
            input_value,
            config=self._config(session_id),
            context=self._context(user_id, model=model),
        )

    def resume(
        self,
        decisions: list[dict[str, Any]],
        *,
        user_id: str = "default",
        session_id: str = "default",
        model: OpenAIModelName | None = None,
    ) -> dict[str, Any]:
        """HITL の判断を渡して同じ thread を再開する。"""
        return self.invoke(
            Command(resume={"decisions": decisions}),
            user_id=user_id,
            session_id=session_id,
            model=model,
        )

    def run(
        self,
        query: str,
        *,
        user_id: str = "default",
        session_id: str = "default",
        model: OpenAIModelName | None = None,
    ) -> str:
        """1 ターン実行し、最終回答テキストを返す。承認待ちなら空文字を返す。"""
        result = self.invoke(query, user_id=user_id, session_id=session_id, model=model)
        if "__interrupt__" in result:
            return ""
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
        """グラフの実行を逐次ストリームする。"""
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
