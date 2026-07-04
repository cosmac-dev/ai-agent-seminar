from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class InputState(TypedDict):
    """グラフへの入力スキーマ。ユーザーメッセージの本文のみを受け取る。
    """

    content: str


class AgentState(TypedDict):
    """短期・長期記憶を扱うエージェントの状態。

    - content: 今ターンのユーザー入力（本文）。ingest_input で messages に変換される。
    - messages: スレッド（短期記憶）内の会話履歴。checkpointer で永続化される。
    - memories: 長期記憶 Store から読み込んだ関連情報。
    - memory_candidates: 今回の会話から抽出された記憶候補。
    - approved_memories: 検証を通過し保存してよいと判定された記憶。
    """

    content: str
    messages: Annotated[list, add_messages]
    memories: list[str]
    memory_candidates: list[str]
    approved_memories: list[str]


@dataclass
class Context:
    """実行ごとに差し替わるコンテキスト。長期記憶の名前空間を決める。"""

    user_id: str
