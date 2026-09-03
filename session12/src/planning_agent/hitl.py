from __future__ import annotations

from typing import Any

from langchain.agents.middleware import HumanInTheLoopMiddleware

APPROVAL_DECISIONS = ["approve", "edit", "reject"]

DEFAULT_HITL_INTERRUPT_ON: dict[str, bool | dict[str, Any]] = {
    "write_file": {"allowed_decisions": APPROVAL_DECISIONS},
    "file_delete": {"allowed_decisions": APPROVAL_DECISIONS},
    "read_file": False,
}

SANDBOX_HITL_INTERRUPT_ON: dict[str, bool | dict[str, Any]] = {
    "shell": {"allowed_decisions": APPROVAL_DECISIONS},
    **DEFAULT_HITL_INTERRUPT_ON,
}


def make_hitl_middleware(
    interrupt_on: dict[str, bool | dict[str, Any]] | None = None,
) -> HumanInTheLoopMiddleware:
    """副作用を伴う Tool 実行前に承認を要求する Middleware を作る。"""
    return HumanInTheLoopMiddleware(
        interrupt_on=interrupt_on or DEFAULT_HITL_INTERRUPT_ON,
        description_prefix="Toolの実行には承認が必要",
    )


def make_sandbox_hitl_middleware(
    interrupt_on: dict[str, bool | dict[str, Any]] | None = None,
) -> HumanInTheLoopMiddleware:
    """サンドボックスの shell 実行も承認対象に含めた Middleware を作る。"""
    return make_hitl_middleware(interrupt_on or SANDBOX_HITL_INTERRUPT_ON)


def decisions_payload(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """`Command(resume=...)` に渡す承認判断の payload を作る。"""
    return {"decisions": decisions}


def approve_all_payload(count: int = 1) -> dict[str, Any]:
    """同時に提示された Tool 呼び出しをすべて承認する payload を作る。"""
    return decisions_payload([{"type": "approve"} for _ in range(count)])
