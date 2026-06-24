from __future__ import annotations

from collections.abc import Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool

from .config import AgentConfig
from .llm import build_llm
from .prompts import DEFAULT_SYSTEM_PROMPT
from .tools import get_default_tools


class Agent:
    """ツールを使う最小の ReAct エージェント。

    使い方::

        from minimal_agent import Agent
        agent = Agent()
        print(agent.run("123 * 7 はいくつ？", verbose=True))
    """

    def __init__(
        self,
        tools: Sequence[BaseTool] | None = None,
        config: AgentConfig | None = None,
        system_prompt: str | None = None,
        llm=None,
    ) -> None:
        self.config = config or AgentConfig()
        self.tools: list[BaseTool] = (
            list(tools) if tools is not None else get_default_tools()
        )
        self._tools_by_name = {t.name: t for t in self.tools}
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        base_llm = llm or build_llm(self.config)
        # ツールをモデルにバインドして、tool_calls を出せるようにする
        self.llm = base_llm.bind_tools(self.tools) if self.tools else base_llm

    def run(self, query: str, *, verbose: bool = False) -> str:
        """1つの要求を ReAct ループで処理し、最終回答（文字列）を返す。

        Args:
            query: ユーザーの要求。
            verbose: True なら思考・行動・観測のトレースを標準出力へ表示する。
        """
        messages: list[BaseMessage] = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=query),
        ]

        for step in range(1, self.config.max_iterations + 1):
            ai_message = self.llm.invoke(messages)
            messages.append(ai_message)

            tool_calls = getattr(ai_message, "tool_calls", None) or []

            # ツール呼び出しが無ければ、それが最終回答
            if not tool_calls:
                if verbose:
                    print(f"[step {step}] 最終回答")
                return _as_text(ai_message)

            if verbose and isinstance(ai_message, AIMessage) and ai_message.content:
                print(f"[step {step}] 思考: {_as_text(ai_message)}")

            # 各ツール呼び出しを実行し、観測を ToolMessage として戻す
            for call in tool_calls:
                name = call["name"]
                args = call.get("args", {})
                if verbose:
                    print(f"[step {step}] 行動: {name}({args})")

                observation = self._invoke_tool(name, args)

                if verbose:
                    print(f"[step {step}] 観測: {observation}")

                messages.append(
                    ToolMessage(content=observation, tool_call_id=call["id"])
                )

        return "（最大反復回数に達したため、回答を確定できなかった。）"

    def _invoke_tool(self, name: str, args: dict) -> str:
        """名前でツールを引き、実行する。失敗しても文字列で観測を返す。"""
        tool = self._tools_by_name.get(name)
        if tool is None:
            return f"エラー: ツール '{name}' は登録されていない。"
        try:
            return str(tool.invoke(args))
        except Exception as exc:  # noqa: BLE001 - 観測としてエラーを返す
            return f"ツール実行エラー: {exc}"


def _as_text(message: BaseMessage) -> str:
    """メッセージの content を素の文字列にする。"""
    content = message.content
    if isinstance(content, str):
        return content
    # 一部プロバイダはリッチな content（list）を返すため連結する
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)
