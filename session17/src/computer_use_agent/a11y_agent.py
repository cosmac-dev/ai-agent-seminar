"""アクセシビリティツリー方式: AT-SPI のアクセシビリティツリーを、LangChain の create_agent で使う。

画面を画像ではなく、AT-SPI で読んだアクセシビリティツリー（テキスト）で渡す。各要素には `[ref=e12]` のような参照が付き、
モデルは参照で操作対象を指定する。実行は、参照した要素の中心の座標を xdotool でクリックする
（Windows なら UI Automation で要素を探し、SendInput で押すのにあたる）。
モデルに Computer Use 専用の機能は要らず、通常の Function Calling で動く。Tool を呼ぶループは create_agent が回す。
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from .computers import DesktopComputer
from .steps import Step, Summary

DEFAULT_MODEL = "gpt-5.4-mini"
SYSTEM_PROMPT = "あなたは利用者の代わりに画面を操作するアシスタント。まず read_screen で画面の要素を読んでから操作する。"

# 操作の前に Tool 呼び出しを検査する関数。引数は (関数名, 引数, 参照した要素または None, 要素のウィンドウ名)。
# 問題なければ None、止めるなら理由を返す（guard.DesktopGuard.check_tool）。
A11yGuard = Callable[[str, dict, dict | None, str], Awaitable[str | None]]


class A11yTools:
    """アクセシビリティツリーを読む Tool と、参照で操作する Tool。最後に読んだアクセシビリティツリーと、途中経過を持つ。"""

    def __init__(self, desktop: DesktopComputer, *, guard: A11yGuard | None = None, settle: float = 0.5,
                 on_step: Callable[[Step], None] | None = None):
        self.desktop = desktop
        self.guard = guard
        self.settle = settle
        self.on_step = on_step
        self.elements: dict = {}
        self.steps: list[Step] = []
        self.tools = self._make_tools()

    async def screen(self) -> str:
        snapshot = await self.desktop.a11y_snapshot()
        self.elements = snapshot["elements"]
        return "現在の画面の要素:\n" + snapshot["text"]

    async def after(self, action: str) -> str:
        """操作の後、画面が落ち着くのを待って記録し、アクセシビリティツリーを返す。"""
        await asyncio.sleep(self.settle)
        step = Step(len(self.steps) + 1, [action], await self.desktop.screenshot())
        self.steps.append(step)
        if self.on_step:
            self.on_step(step)
        return "OK\n" + await self.screen()

    async def refused(self, name: str, args: dict) -> str | None:
        element = self.elements.get(args.get("ref", ""))
        if self.guard and (reason := await self.guard(name, args, element, (element or {}).get("window", ""))):
            return f"実行していない。理由: {reason}。同じ操作を繰り返さず、作業を止めて状況を報告すること。"
        return None

    async def press(self, name: str, ref: str) -> str:
        if ref not in self.elements:
            return f"失敗: {ref} は現在のアクセシビリティツリーにない。read_screen で読み直すこと。"
        if message := await self.refused(name, {"ref": ref}):
            return message
        e = self.elements[ref]
        x, y = e["x"] + e["width"] // 2, e["y"] + e["height"] // 2  # 要素の中心を押す
        if name == "double_click":
            await self.desktop.double_click(x, y)
        else:
            await self.desktop.click(x, y, "right" if name == "right_click" else "left")
        return await self.after(f'{name}({ref} "{e["name"]}")')

    def _make_tools(self) -> list:
        @tool
        async def read_screen() -> str:
            """画面に表示されているアクセシビリティツリーを読む。操作できる要素には [ref=e12] のような参照が付く。"""
            return await self.screen()

        @tool
        async def click(ref: str) -> str:
            """参照で指定した要素をクリックする。"""
            return await self.press("click", ref)

        @tool
        async def double_click(ref: str) -> str:
            """参照で指定した要素をダブルクリックする（ファイルを開くなど）。"""
            return await self.press("double_click", ref)

        @tool
        async def right_click(ref: str) -> str:
            """参照で指定した要素を右クリックして、メニューを開く。"""
            return await self.press("right_click", ref)

        @tool
        async def type_text(text: str) -> str:
            """キーボードで文字を入力する。文字は、フォーカスのある入力欄のカーソルの位置（アクセシビリティツリーの caret=位置/文字数）に入る。
            入力する前に caret を確かめ、必要なら press_key で移動する（文書の末尾は CTRL+END）。"""
            await self.desktop.type(text)
            return await self.after(f"type_text({text!r})")

        @tool
        async def press_key(keys: list[str]) -> str:
            """キーを押す。同時に押すキーを並べる（例: ["CTRL", "S"]、["ENTER"]）。"""
            if message := await self.refused("press_key", {"keys": keys}):
                return message
            await self.desktop.keypress(keys)
            return await self.after("press_key(" + "+".join(keys) + ")")

        return [read_screen, click, double_click, right_click, type_text, press_key]


async def run_a11y_agent(task: str | list, tools: A11yTools, *, model: str = DEFAULT_MODEL,
                         system_prompt: str = SYSTEM_PROMPT, recursion_limit: int = 60):
    """アクセシビリティツリーの Agent を作って実行する。(create_agent の結果の状態, Summary) を返す。

    続きを依頼するときは、task に前回の結果の messages と新しい依頼を並べたリストを渡す。
    """
    messages = [{"role": "user", "content": task}] if isinstance(task, str) else list(task)
    # 画面の操作は順番が大事なので、Tool を同時に呼ばせない（create_agent はまとめて呼ばれた Tool を並行して実行する）
    llm = ChatOpenAI(model=model, model_kwargs={"parallel_tool_calls": False})
    agent = create_agent(llm, tools=tools.tools, system_prompt=system_prompt)
    started, first_step = time.perf_counter(), len(tools.steps)
    result = await agent.ainvoke({"messages": messages}, {"recursion_limit": recursion_limit})
    replies = [m for m in result["messages"][len(messages):] if m.type == "ai"]  # 今回の応答だけを数える
    return result, Summary(result["messages"][-1].text, tools.steps[first_step:], len(replies),
                           sum((m.usage_metadata or {}).get("input_tokens", 0) for m in replies),
                           sum((m.usage_metadata or {}).get("output_tokens", 0) for m in replies),
                           time.perf_counter() - started)
