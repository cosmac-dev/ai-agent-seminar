from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from .memory import (
    load_memory,
    make_extract_memory,
    validate_memory,
    write_memory,
)
from .state import AgentState, Context, InputState
from .tools import DEFAULT_TOOLS

DEFAULT_SYSTEM_PROMPT = (
    "あなたは有能なAIエージェントです。\n"
    "計算は推測せず必ず calculator ツールを使ってください。\n"
    "取り込み済みドキュメント（社内規程・マニュアル等）に関する質問は、"
    "推測せず search_knowledge_base ツールで関連箇所を検索してから、"
    "検索結果を根拠に答えてください。\n"
    "検索結果に根拠が無いことは分からないと答え、最後は日本語で簡潔に答えてください。"
)


def make_call_model(model: BaseChatModel, tools, system_prompt: str):
    """長期記憶をプロンプトに差し込む ReAct 用 LLM node を生成する。"""
    model_with_tools = model.bind_tools(tools)

    def call_model(state: AgentState) -> AgentState:
        memory_text = "\n".join(f"- {m}" for m in state.get("memories", []))
        if not memory_text:
            memory_text = "なし"

        system = SystemMessage(
            content=f"{system_prompt}\n\n参考になる長期記憶:\n{memory_text}"
        )
        response = model_with_tools.invoke([system] + state["messages"])
        return {"messages": [response]}

    return call_model


def build_state_graph(
    model: BaseChatModel,
    *,
    tools=None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> StateGraph:
    """未コンパイルの `StateGraph`（グラフ定義）を構築する。

    ライブラリ用途と LangGraph Server 用途で共有する“定義の単一の源”。
    コンパイル（＝永続化の差し込み）はここでは行わない。

    入力スキーマ（InputState）は `messages`（会話履歴）。
    ユーザー発話を HumanMessage として渡し、checkpointer がスレッドごとの
    会話履歴を保持する。

    フロー:
        START → load_memory → call_model ⇄ tools
        call_model が終端に達したら extract_memory → validate_memory → write_memory → END
    """
    tools = tools if tools is not None else DEFAULT_TOOLS

    call_model = make_call_model(model, tools, system_prompt)
    extract_memory = make_extract_memory(model)

    builder = StateGraph(AgentState, input_schema=InputState, context_schema=Context)

    builder.add_node("load_memory", load_memory)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("extract_memory", extract_memory)
    builder.add_node("validate_memory", validate_memory)
    builder.add_node("write_memory", write_memory)

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "call_model")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
        {"tools": "tools", END: "extract_memory"},
    )
    builder.add_edge("tools", "call_model")
    builder.add_edge("extract_memory", "validate_memory")
    builder.add_edge("validate_memory", "write_memory")
    builder.add_edge("write_memory", END)

    return builder


def build_graph(
    model: BaseChatModel,
    *,
    tools=None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    checkpointer: BaseCheckpointSaver | None = None,
    store: BaseStore | None = None,
):
    """ライブラリ用途：自前で永続化を差し込んでコンパイル済みグラフを返す。

    - 短期記憶: checkpointer が messages をスレッド単位で永続化する。
    - 長期記憶: store がユーザー単位で恒常的な事実を保存・検索する。

    どちらも省略時は InMemory 実装を使う。LangGraph Server 上で動かす場合は
    永続化はサーバーが所有するため、この関数ではなく `server.make_graph` を使う。
    """
    checkpointer = checkpointer if checkpointer is not None else InMemorySaver()
    store = store if store is not None else InMemoryStore()

    builder = build_state_graph(model, tools=tools, system_prompt=system_prompt)
    return builder.compile(checkpointer=checkpointer, store=store)
