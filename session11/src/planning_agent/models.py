from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .state import NextAction


class GoalSpec(BaseModel):
    """ユーザー依頼から抽出した目的と成功条件。"""

    objective: str = Field(description="達成すべき最終状態。1文で具体的に書く。")
    success_criteria: list[str] = Field(
        description="完了判定に使う観測可能な成功条件。3から5件。"
    )
    constraints: list[str] = Field(
        description="守るべき制約、禁止事項、確認が必要な条件。"
    )


class WorkPlan(BaseModel):
    """目的を達成するための実行計画。"""

    steps: list[str] = Field(description="実行順の具体的なステップ。3から6件。")


class StepCritique(BaseModel):
    """ステップの成果物に対する批評。"""

    verdict: Literal["accept", "revise"] = Field(
        description="ステップの目的を満たしていれば accept、やり直すべきなら revise。"
    )
    issues: list[str] = Field(description="不足している点。accept のときは空。")
    guidance: str = Field(description="やり直す場合の指示。1文。")


class MonitorDecision(BaseModel):
    """実行結果を監視した後の制御判断。"""

    next_action: NextAction = Field(
        description="次に進む、再計画する、完了する、人間へ戻す、のいずれか。"
    )
    completed_step_summary: str = Field(description="直近ステップで完了したこと。")
    remaining_gaps: list[str] = Field(description="未達の成功条件や不確実な点。")
    reason: str = Field(description="判断理由。観測結果に基づいて簡潔に書く。")
