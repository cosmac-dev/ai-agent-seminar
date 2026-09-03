from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from langchain.agents.middleware import (
    CodexSandboxExecutionPolicy,
    DockerExecutionPolicy,
    HostExecutionPolicy,
    ShellToolMiddleware,
)

ExecutionPolicyName = Literal["host", "docker", "codex"]
DEFAULT_EXECUTION_POLICY: ExecutionPolicyName = "host"
SANDBOX_IMAGE = "python:3.12-alpine"
SANDBOX_LABEL = "ai-agent-seminar=session11"

COMMON_LIMITS = {
    "command_timeout": 15.0,
    "startup_timeout": 60.0,
    "max_output_lines": 50,
    "max_output_bytes": 4_000,
}


@dataclass(frozen=True)
class ShellSessionSpec:
    """ExecutionPolicy ごとに変わるシェルセッションの設定。"""

    policy: Any
    shell_command: str
    startup_commands: tuple[str, ...]
    note: str


def make_host_policy() -> HostExecutionPolicy:
    """ホストプロセスで実行する Policy を作る。隔離は資源上限のみ。"""
    return HostExecutionPolicy(
        cpu_time_seconds=10,
        memory_bytes=1024 * 1024 * 1024,
        **COMMON_LIMITS,
    )


def make_docker_policy() -> DockerExecutionPolicy:
    """専用 Docker コンテナへ隔離する Policy を作る。"""
    return DockerExecutionPolicy(
        image=SANDBOX_IMAGE,
        network_enabled=False,
        read_only_rootfs=True,
        user="65534:65534",
        memory_bytes=256 * 1024 * 1024,
        cpus="0.5",
        extra_run_args=(
            f"--label={SANDBOX_LABEL}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges=true",
            "--pids-limit=64",
        ),
        **COMMON_LIMITS,
    )


def make_codex_policy() -> CodexSandboxExecutionPolicy:
    """Codex CLI のサンドボックスへ委ねる Policy を作る。"""
    return CodexSandboxExecutionPolicy(
        platform="auto",
        config_overrides={"sandbox_workspace_write.network_access": False},
        **COMMON_LIMITS,
    )


def make_shell_session_spec(
    execution_policy: ExecutionPolicyName = DEFAULT_EXECUTION_POLICY,
) -> ShellSessionSpec:
    """指定された ExecutionPolicy 用の shell Tool 設定を返す。"""
    if execution_policy == "docker":
        return ShellSessionSpec(
            policy=make_docker_policy(),
            shell_command="/bin/sh",
            startup_commands=("cd /tmp",),
            note="""shell Tool は隔離コンテナ内の /bin/sh セッションで、次の制約がある。
- bash は無い。POSIX sh の構文で書く
- 書き込めるのは /tmp だけ。ルートファイルシステムは読み取り専用
- 外部ネットワークへは接続できない""",
        )

    if execution_policy == "codex":
        return ShellSessionSpec(
            policy=make_codex_policy(),
            shell_command="/bin/bash",
            startup_commands=(),
            note="""shell Tool は Codex CLI のサンドボックス内の /bin/bash セッション。
- ホスト上で動くが、syscall とファイルアクセスが制限されている
- 書き込めるのは作業ディレクトリと /tmp だけ
- 外部ネットワークへは接続できない""",
        )

    return ShellSessionSpec(
        policy=make_host_policy(),
        shell_command="/bin/bash",
        startup_commands=(),
        note="""shell Tool はホスト上の /bin/bash セッションで、隔離されていない。
- 作業ディレクトリは一時ディレクトリ。その外のファイルは変更しない
- 外部ネットワークへ接続できる""",
    )


def make_shell_middleware(
    execution_policy: ExecutionPolicyName = DEFAULT_EXECUTION_POLICY,
) -> tuple[ShellToolMiddleware, ShellSessionSpec]:
    """ExecutionPolicy を設定した ShellToolMiddleware と説明用 spec を返す。"""
    spec = make_shell_session_spec(execution_policy)
    middleware = ShellToolMiddleware(
        execution_policy=spec.policy,
        shell_command=spec.shell_command,
        startup_commands=spec.startup_commands,
        # workspace_root と env を渡さず、ホストの作業ディレクトリや API キーを渡さない。
    )
    return middleware, spec
