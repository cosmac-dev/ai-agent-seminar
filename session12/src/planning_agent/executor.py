"""計画ループの実行部（第9回・第10回で組み立てた ReAct サブグラフ）。

`make_guarded_agent()` は `create_agent()` の ReAct サブグラフに、長期記憶の
プロンプト差し込み、モデル選択、サンドボックス付き shell Tool、Tool 実行前の
承認（HITL）を載せて返す。Planning グラフの `agent` ノードへそのまま置ける。
"""

from __future__ import annotations

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, dynamic_prompt
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from .hitl import make_sandbox_hitl_middleware
from .sandbox import (
    DEFAULT_EXECUTION_POLICY,
    ExecutionPolicyName,
    make_shell_middleware,
)
from .state import DEFAULT_MODEL, Context, LongTermMemoryState
from .tools import DEFAULT_TOOLS, without_host_execution_tools

DEFAULT_SYSTEM_PROMPT = (
    "あなたはAIエージェントです。\n"
    "必要な場合はToolを利用してください。\n\n"
    "コマンドやコードの実行には shell Tool だけを使うこと。\n"
    "出力が改行で終わるコマンドを使うこと。"
)


def _chat_model(model_name: str) -> BaseChatModel:
    """Assistant / Context で選ばれたモデル名から ChatOpenAI を作る。"""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model_name or DEFAULT_MODEL, temperature=0)


def make_model_selector_middleware():
    """実行時 Context のモデル名で ReAct サブグラフのモデルを差し替える。"""

    class ModelSelectorMiddleware(AgentMiddleware):
        state_schema = LongTermMemoryState

        @staticmethod
        def _select_model(request):
            model_name = getattr(request.runtime.context, "model", DEFAULT_MODEL)
            try:
                from langchain_openai import ChatOpenAI
            except Exception:  # noqa: BLE001 - テスト用モデルなどでは差し替えない
                ChatOpenAI = None

            if ChatOpenAI is not None and isinstance(request.model, ChatOpenAI):
                request.model = _chat_model(model_name)

        def wrap_model_call(self, request, handler):
            self._select_model(request)
            return handler(request)

        async def awrap_model_call(self, request, handler):
            self._select_model(request)
            return await handler(request)

    return ModelSelectorMiddleware()


def make_memory_prompt_middleware(system_prompt: str, policy_note: str):
    """長期記憶とサンドボックス制約を system prompt に差し込む。"""

    @dynamic_prompt
    def memory_system_prompt(request: ModelRequest) -> str:
        memories = request.state.get("memories", [])
        prompt = f"{system_prompt}\n{policy_note}"
        if memories:
            memory_text = "\n".join(f"- {memory}" for memory in memories)
            prompt += f"\n\n参考になる長期記憶:\n{memory_text}"
        return prompt

    return memory_system_prompt


def make_guarded_agent(
    model: BaseChatModel,
    *,
    tools: Sequence[BaseTool] | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    execution_policy: ExecutionPolicyName = DEFAULT_EXECUTION_POLICY,
):
    """HITL とサンドボックス付きの ReAct サブグラフを作る。"""
    safe_tools = without_host_execution_tools(tools or DEFAULT_TOOLS)
    shell_middleware, shell_spec = make_shell_middleware(execution_policy)

    return create_agent(
        model=model,
        tools=safe_tools,
        state_schema=LongTermMemoryState,
        context_schema=Context,
        middleware=[
            make_memory_prompt_middleware(system_prompt, shell_spec.note),
            make_model_selector_middleware(),
            shell_middleware,
            make_sandbox_hitl_middleware(),
        ],
    )
