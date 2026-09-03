from __future__ import annotations

from typing import Literal

from guarded_agent.state import InputState, LongTermMemoryState
from typing_extensions import NotRequired


NextAction = Literal["continue", "replan", "complete", "escalate"]


class PlanningInputState(InputState, total=False):
    """Planning Agent の入力。

    `user_request` を省略した場合は、最後の HumanMessage を依頼として使う。
    """

    user_request: NotRequired[str]
    user_id: NotRequired[str]
    max_replans: NotRequired[int]
    max_steps: NotRequired[int]
    max_reflections: NotRequired[int]


class PlanningAgentState(LongTermMemoryState, total=False):
    """Goal Setting、Planning、Reflection、Monitoring を追加したエージェント状態。"""

    user_request: str
    user_id: str
    objective: str
    success_criteria: list[str]
    constraints: list[str]
    plan: list[str]
    current_step_index: int
    critique: str
    revision_notes: list[str]
    reflection_count: int
    max_reflections: int
    completed_steps: list[str]
    observations: list[str]
    last_result: str
    monitor_reason: str
    remaining_gaps: list[str]
    next_action: NextAction
    replan_count: int
    max_replans: int
    max_steps: int
    final_answer: str
    escalated: bool
    human_note: NotRequired[str]
