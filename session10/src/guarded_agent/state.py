from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict

from langchain.agents.middleware import AgentState as MiddlewareAgentState
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired

# Assistant 設定 / Context で選択可能な OpenAI チャットモデル
# ChatOpenAI（Chat Completions）向け。Responses API 専用の *-pro は含めない。
DEFAULT_MODEL = "gpt-5.4-mini"
OpenAIModelName = Literal[
    "gpt-5.6",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4o-mini",
    "gpt-4o",
]


class InputState(TypedDict):
    """グラフへの入力スキーマ。会話メッセージ列を受け取る。"""

    messages: Annotated[list[AnyMessage], add_messages]


class LongTermMemoryState(MiddlewareAgentState, total=False):
    """HITL・サンドボックス付きエージェントの状態。

    `create_agent()` の標準状態に、長期記憶用の一時フィールドを追加する。
    """

    memories: NotRequired[list[str]]
    memory_candidates: NotRequired[list[str]]
    approved_memories: NotRequired[list[str]]


# 後続ノードの型注釈用。公開名は旧実装と同じにしておく。
AgentState = LongTermMemoryState


@dataclass
class Context:
    """実行ごとに差し替わるコンテキスト。

    - user_id: 長期記憶の名前空間を決める。
    - model: ReAct サブグラフが使う OpenAI モデル名。
    """

    user_id: str
    model: OpenAIModelName = DEFAULT_MODEL
