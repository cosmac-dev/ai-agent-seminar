from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.types import interrupt

from .executor import DEFAULT_SYSTEM_PROMPT, make_guarded_agent
from .memory import (
    load_memory,
    make_extract_memory,
    validate_memory,
    write_memory,
)
from .models import GoalSpec, MonitorDecision, StepCritique, WorkPlan
from .sandbox import DEFAULT_EXECUTION_POLICY, ExecutionPolicyName
from .state import Context, PlanningAgentState, PlanningInputState
from .tools import DEFAULT_TOOLS


def _bullet_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- なし"


def _numbered_lines(items: list[str]) -> str:
    if not items:
        return "なし"
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))


def _last_human_text(state: PlanningAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage) and message.content:
            return str(message.content)
    return ""


def _last_ai_text(state: PlanningAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage) and message.content:
            return str(message.content)
    return "最終応答を取得できなかった。"


def _current_step(state: PlanningAgentState) -> str:
    index = state.get("current_step_index", 0)
    plan = state.get("plan", [])
    if index >= len(plan):
        return "追加で実行するステップはない。"
    return plan[index]


def _make_goal_setting(model: BaseChatModel):
    goal_setter = model.with_structured_output(GoalSpec)

    def goal_setting(
        state: PlanningAgentState,
        runtime: Runtime[Context],
    ) -> dict:
        user_request = state.get("user_request") or _last_human_text(state)
        if not user_request:
            raise ValueError("user_request または HumanMessage が必要です。")

        result = goal_setter.invoke(
            [
                (
                    "system",
                    "ユーザー依頼を、実行可能な目的、観測可能な成功条件、"
                    "制約へ分解する。危険な操作や曖昧な判断は制約に含める。",
                ),
                ("user", user_request),
            ]
        )
        return {
            "user_request": user_request,
            "user_id": runtime.context.user_id,
            "objective": result.objective,
            "success_criteria": result.success_criteria,
            "constraints": result.constraints,
            "plan": [],
            "current_step_index": 0,
            "completed_steps": [],
            "observations": [],
            "last_result": "",
            "critique": "",
            "revision_notes": [],
            "reflection_count": 0,
            "monitor_reason": "",
            "remaining_gaps": [],
            "next_action": "continue",
            "replan_count": 0,
            "max_replans": state.get("max_replans", 2),
            "max_steps": state.get("max_steps", 8),
            "max_reflections": state.get("max_reflections", 1),
            "final_answer": "",
            "escalated": False,
        }

    return goal_setting


def _make_plan_task(model: BaseChatModel):
    planner = model.with_structured_output(WorkPlan)

    def plan_task(state: PlanningAgentState) -> dict:
        result = planner.invoke(
            [
                (
                    "system",
                    "目的を達成するための実行計画を作る。Tool 実行が必要な"
                    "作業は、何を確認してから実行するかも含める。",
                ),
                (
                    "user",
                    f"Objective:\n{state['objective']}\n\n"
                    f"Success Criteria:\n"
                    f"{_bullet_lines(state['success_criteria'])}\n\n"
                    f"Constraints:\n{_bullet_lines(state['constraints'])}",
                ),
            ]
        )
        return {
            "plan": result.steps,
            "current_step_index": 0,
        }

    return plan_task


def execute_step(state: PlanningAgentState) -> dict:
    """現在の計画ステップを、HITL + Sandbox 付き agent へ渡す。"""
    instruction = f"""あなたは大きなタスクの1ステップだけを担当する実行エージェントです。

Objective:
{state['objective']}

Success Criteria:
{_bullet_lines(state['success_criteria'])}

Constraints:
{_bullet_lines(state['constraints'])}

Current Step:
{_current_step(state)}

これまでの完了ステップ:
{_bullet_lines(state.get('completed_steps', []))}
"""
    if state.get("critique"):
        instruction += (
            f"\n前回の成果物への指摘:\n{state['critique']}\n"
            "この指摘を反映して、同じステップをやり直す。\n"
        )
    instruction += """
必要な場合だけ Tool を使う。コマンドやコード実行は shell Tool だけを使う。
このステップで実行したこと、観測した結果、残った不確実性を簡潔に報告する。
"""
    return {"messages": [HumanMessage(content=instruction)]}


def collect_step_result(state: PlanningAgentState) -> dict:
    """実行部の最後の応答を、このステップの成果物として取り出す。

    完了ステップと観測の記録は monitor_progress が行う。Reflection で同じ
    ステップをやり直すことがあるため、ここで記録すると進捗が二重に進む。
    """
    return {"last_result": _last_ai_text(state)}


def _make_reflect_step(model: BaseChatModel):
    critic = model.with_structured_output(StepCritique)

    def reflect_step(state: PlanningAgentState) -> dict:
        memories = state.get("memories", [])
        memory_note = (
            f"\n\nユーザーについて分かっていること:\n{_bullet_lines(memories)}"
            if memories
            else ""
        )

        result = critic.invoke(
            [
                (
                    "system",
                    "ステップの成果物を、そのステップの目的と成功条件に照らして"
                    "批評する。根拠のない accept は禁止。指摘は1件に絞る。",
                ),
                (
                    "user",
                    f"Objective:\n{state['objective']}\n\n"
                    f"Success Criteria:\n"
                    f"{_bullet_lines(state['success_criteria'])}\n\n"
                    f"Current Step:\n{_current_step(state)}\n\n"
                    f"過去に受けた指摘:\n"
                    f"{_bullet_lines(state.get('revision_notes', []))}"
                    f"{memory_note}\n\n"
                    f"成果物:\n{state['last_result']}",
                ),
            ]
        )
        if result.verdict == "accept":
            return {"critique": ""}
        return {
            "critique": "\n".join(result.issues + [result.guidance]),
            "revision_notes": state.get("revision_notes", []) + result.issues,
            "reflection_count": state.get("reflection_count", 0) + 1,
        }

    return reflect_step


def route_after_reflect(
    state: PlanningAgentState,
) -> Literal["execute_step", "monitor_progress"]:
    reflections = state.get("reflection_count", 0)
    if state.get("critique") and reflections <= state.get("max_reflections", 1):
        return "execute_step"
    return "monitor_progress"


def _make_monitor_progress(model: BaseChatModel):
    monitor = model.with_structured_output(MonitorDecision)

    def monitor_progress(state: PlanningAgentState) -> dict:
        next_step_index = state.get("current_step_index", 0) + 1
        completed = state.get("completed_steps", []) + [
            f"{next_step_index}. {_current_step(state)}"
        ]
        observations = state.get("observations", []) + [state["last_result"]]

        # ステップを1つ進め、Reflection のカウンタを次のステップ用に戻す
        progress = {
            "completed_steps": completed,
            "observations": observations,
            "current_step_index": next_step_index,
            "reflection_count": 0,
            "critique": "",
        }

        if len(observations) >= state.get("max_steps", 8):
            return {
                **progress,
                "next_action": "escalate",
                "monitor_reason": "最大ステップ数に到達したため、人間の判断へ戻す。",
                "remaining_gaps": state.get("success_criteria", []),
            }

        decision = monitor.invoke(
            [
                (
                    "system",
                    "実行結果を成功条件に照らして監視する。根拠が弱い完了判定は"
                    "禁止。危険、曖昧、承認拒否、同じ失敗の反復は escalate を選ぶ。",
                ),
                (
                    "user",
                    f"Objective:\n{state['objective']}\n\n"
                    f"Success Criteria:\n"
                    f"{_bullet_lines(state['success_criteria'])}\n\n"
                    f"Plan:\n{_numbered_lines(state['plan'])}\n\n"
                    f"Completed Steps:\n{_bullet_lines(completed)}\n\n"
                    f"Latest Observation:\n{state['last_result']}\n\n"
                    f"Previous Observations:\n"
                    f"{_bullet_lines(observations[:-1])}",
                ),
            ]
        )
        return {
            **progress,
            "next_action": decision.next_action,
            "monitor_reason": decision.reason,
            "remaining_gaps": decision.remaining_gaps,
        }

    return monitor_progress


def _make_replan_task(model: BaseChatModel):
    planner = model.with_structured_output(WorkPlan)

    def replan_task(state: PlanningAgentState) -> dict:
        if state.get("replan_count", 0) >= state.get("max_replans", 2):
            return {
                "next_action": "escalate",
                "monitor_reason": "再計画回数が上限に達した。",
            }

        result = planner.invoke(
            [
                (
                    "system",
                    "観測結果と未達条件をもとに、残作業だけの計画へ更新する。"
                    "すでに完了した作業を繰り返さない。",
                ),
                (
                    "user",
                    f"Objective:\n{state['objective']}\n\n"
                    f"Success Criteria:\n"
                    f"{_bullet_lines(state['success_criteria'])}\n\n"
                    f"Completed Steps:\n"
                    f"{_bullet_lines(state.get('completed_steps', []))}\n\n"
                    f"Observations:\n"
                    f"{_bullet_lines(state.get('observations', []))}\n\n"
                    f"Remaining Gaps:\n"
                    f"{_bullet_lines(state.get('remaining_gaps', []))}\n\n"
                    f"Monitoring Reason:\n{state.get('monitor_reason', '')}",
                ),
            ]
        )
        return {
            "plan": result.steps,
            "current_step_index": 0,
            "replan_count": state.get("replan_count", 0) + 1,
            "next_action": "continue",
        }

    return replan_task


def human_escalation(state: PlanningAgentState) -> dict:
    response = interrupt(
        {
            "kind": "planner_escalation",
            "objective": state.get("objective"),
            "success_criteria": state.get("success_criteria", []),
            "completed_steps": state.get("completed_steps", []),
            "observations": state.get("observations", []),
            "remaining_gaps": state.get("remaining_gaps", []),
            "reason": state.get("monitor_reason", "人間の判断が必要"),
            "allowed_decisions": ["continue", "revise_plan", "finish"],
        }
    )
    decision_type = response.get("type")
    if decision_type == "finish":
        return {
            "next_action": "complete",
            "final_answer": response.get("final_answer", "人間判断により完了。"),
            "escalated": True,
            "human_note": response.get("message", "人間判断により完了。"),
        }
    if decision_type == "revise_plan":
        return {
            "next_action": "replan",
            "monitor_reason": response.get("message", "人間判断により再計画。"),
            "escalated": True,
            "human_note": response.get("message", ""),
        }
    if decision_type == "continue":
        return {
            "next_action": "continue",
            "escalated": True,
            "human_note": response.get("message", "人間判断により継続。"),
        }
    raise ValueError(f"未対応の人間判断です: {decision_type}")


def _make_finalize(model: BaseChatModel):
    def finalize(state: PlanningAgentState) -> dict:
        if state.get("final_answer"):
            return {"final_answer": state["final_answer"]}

        response = model.invoke(
            [
                (
                    "system",
                    "Planner エージェントの最終報告を日本語で簡潔に作る。"
                    "完了したこと、根拠、残リスクを分けて書く。",
                ),
                (
                    "user",
                    f"Objective:\n{state.get('objective')}\n\n"
                    f"Success Criteria:\n"
                    f"{_bullet_lines(state.get('success_criteria', []))}\n\n"
                    f"Completed Steps:\n"
                    f"{_bullet_lines(state.get('completed_steps', []))}\n\n"
                    f"Observations:\n"
                    f"{_bullet_lines(state.get('observations', []))}\n\n"
                    f"Remaining Gaps:\n"
                    f"{_bullet_lines(state.get('remaining_gaps', []))}\n\n"
                    f"Monitoring Reason:\n{state.get('monitor_reason', '')}",
                ),
            ]
        )
        return {"final_answer": str(response.content)}

    return finalize


def route_after_monitor(
    state: PlanningAgentState,
) -> Literal["execute_step", "replan_task", "human_escalation", "finalize"]:
    action = state.get("next_action", "continue")
    if action == "complete":
        return "finalize"
    if action == "escalate":
        return "human_escalation"
    if action == "replan":
        return "replan_task"
    if state.get("current_step_index", 0) >= len(state.get("plan", [])):
        return "finalize"
    return "execute_step"


def route_after_replan(
    state: PlanningAgentState,
) -> Literal["execute_step", "human_escalation"]:
    if state.get("next_action") == "escalate":
        return "human_escalation"
    return "execute_step"


def route_after_human(
    state: PlanningAgentState,
) -> Literal["execute_step", "replan_task", "finalize"]:
    action = state.get("next_action", "continue")
    if action == "complete":
        return "finalize"
    if action == "replan":
        return "replan_task"
    if state.get("current_step_index", 0) >= len(state.get("plan", [])):
        return "finalize"
    return "execute_step"


def build_state_graph(
    model: BaseChatModel,
    *,
    tools: Sequence[BaseTool] | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    execution_policy: ExecutionPolicyName = DEFAULT_EXECUTION_POLICY,
) -> StateGraph:
    """session09 のグラフへ Goal Setting、Planning、Monitoring を追加する。"""
    agent = make_guarded_agent(
        model,
        tools=tools or DEFAULT_TOOLS,
        system_prompt=system_prompt,
        execution_policy=execution_policy,
    )

    builder = StateGraph(
        PlanningAgentState,
        input_schema=PlanningInputState,
        context_schema=Context,
    )
    builder.add_node("load_memory", load_memory)
    builder.add_node("goal_setting", _make_goal_setting(model))
    builder.add_node("plan_task", _make_plan_task(model))
    builder.add_node("execute_step", execute_step)
    builder.add_node("agent", agent)
    builder.add_node("collect_step_result", collect_step_result)
    builder.add_node("reflect_step", _make_reflect_step(model))
    builder.add_node("monitor_progress", _make_monitor_progress(model))
    builder.add_node("replan_task", _make_replan_task(model))
    builder.add_node("human_escalation", human_escalation)
    builder.add_node("finalize", _make_finalize(model))
    builder.add_node("extract_memory", make_extract_memory(model))
    builder.add_node("validate_memory", validate_memory)
    builder.add_node("write_memory", write_memory)

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "goal_setting")
    builder.add_edge("goal_setting", "plan_task")
    builder.add_edge("plan_task", "execute_step")
    builder.add_edge("execute_step", "agent")
    builder.add_edge("agent", "collect_step_result")
    builder.add_edge("collect_step_result", "reflect_step")
    builder.add_conditional_edges(
        "reflect_step",
        route_after_reflect,
        {
            "execute_step": "execute_step",
            "monitor_progress": "monitor_progress",
        },
    )
    builder.add_conditional_edges(
        "monitor_progress",
        route_after_monitor,
        {
            "execute_step": "execute_step",
            "replan_task": "replan_task",
            "human_escalation": "human_escalation",
            "finalize": "finalize",
        },
    )
    builder.add_conditional_edges(
        "replan_task",
        route_after_replan,
        {
            "execute_step": "execute_step",
            "human_escalation": "human_escalation",
        },
    )
    builder.add_conditional_edges(
        "human_escalation",
        route_after_human,
        {
            "execute_step": "execute_step",
            "replan_task": "replan_task",
            "finalize": "finalize",
        },
    )
    builder.add_edge("finalize", "extract_memory")
    builder.add_edge("extract_memory", "validate_memory")
    builder.add_edge("validate_memory", "write_memory")
    builder.add_edge("write_memory", END)
    return builder


def build_graph(
    model: BaseChatModel,
    *,
    tools: Sequence[BaseTool] | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    execution_policy: ExecutionPolicyName = DEFAULT_EXECUTION_POLICY,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
):
    """永続化を差し込んだ Planning Agent グラフを返す。"""
    builder = build_state_graph(
        model,
        tools=tools,
        system_prompt=system_prompt,
        execution_policy=execution_policy,
    )
    return builder.compile(
        checkpointer=checkpointer if checkpointer is not None else InMemorySaver(),
        store=store if store is not None else InMemoryStore(),
    )
