from __future__ import annotations

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt, wrap_model_call
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from .hitl import make_sandbox_hitl_middleware
from .memory import (
    load_memory,
    make_extract_memory,
    validate_memory,
    write_memory,
)
from .sandbox import (
    DEFAULT_EXECUTION_POLICY,
    ExecutionPolicyName,
    make_shell_middleware,
)
from .state import DEFAULT_MODEL, Context, InputState, LongTermMemoryState
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

    @wrap_model_call(state_schema=LongTermMemoryState)
    def select_model(request, handler):
        model_name = getattr(request.runtime.context, "model", DEFAULT_MODEL)
        try:
            from langchain_openai import ChatOpenAI
        except Exception:  # noqa: BLE001 - テスト用モデルなどでは差し替えない
            ChatOpenAI = None

        if ChatOpenAI is not None and isinstance(request.model, ChatOpenAI):
            request.model = _chat_model(model_name)
        return handler(request)

    return select_model


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


def build_state_graph(
    model: BaseChatModel,
    *,
    tools: Sequence[BaseTool] | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    execution_policy: ExecutionPolicyName = DEFAULT_EXECUTION_POLICY,
) -> StateGraph:
    """未コンパイルの `StateGraph`（グラフ定義）を構築する。

    フロー:
        START → load_memory → agent(create_agent + HITL + sandbox)
        → extract_memory → validate_memory → write_memory → END
    """
    agent = make_guarded_agent(
        model,
        tools=tools,
        system_prompt=system_prompt,
        execution_policy=execution_policy,
    )
    extract_memory = make_extract_memory(model)

    builder = StateGraph(
        LongTermMemoryState,
        input_schema=InputState,
        context_schema=Context,
    )
    builder.add_node("load_memory", load_memory)
    builder.add_node("agent", agent)
    builder.add_node("extract_memory", extract_memory)
    builder.add_node("validate_memory", validate_memory)
    builder.add_node("write_memory", write_memory)

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "agent")
    builder.add_edge("agent", "extract_memory")
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
    """ライブラリ用途：永続化を差し込んでコンパイル済みグラフを返す。"""
    checkpointer = checkpointer if checkpointer is not None else InMemorySaver()
    store = store if store is not None else InMemoryStore()

    builder = build_state_graph(
        model,
        tools=tools,
        system_prompt=system_prompt,
        execution_policy=execution_policy,
    )
    return builder.compile(checkpointer=checkpointer, store=store)


# Notebook とサーバー側で意図が読みやすい名前も公開する。
build_sandbox_state_graph = build_state_graph
build_sandbox_graph = build_graph
