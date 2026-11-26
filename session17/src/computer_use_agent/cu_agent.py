"""スクリーンショット方式: OpenAI の computer tool を、OpenAI Agents SDK で使う。

ループ（computer_call を受け取り、行動を実行し、スクリーンショットを返す）は Agents SDK の Runner が回す。
ここでは、行動を実行する `AsyncComputer` を、仮想デスクトップの `DesktopComputer` で実装する。
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Callable

from agents import Agent, AsyncComputer, ComputerTool, Runner

from .computers import DesktopComputer
from .guard import ActionRefused, DesktopGuard
from .steps import Step, Summary

DEFAULT_MODEL = "gpt-5.5"  # 小さいモデルは座標の読み違いが多い


class SdkDesktop(AsyncComputer):
    """DesktopComputer を Agents SDK の AsyncComputer の形に合わせる。

    guard を渡すと、取り消しにくい操作の前で確認し、拒否されたら ActionRefused を投げて実行を止める
    （computer tool には、行動ごとに承認を挟む仕組みがないため）。
    """

    def __init__(self, desktop: DesktopComputer, *, guard: DesktopGuard | None = None, settle: float = 0.5,
                 on_step: Callable[[Step], None] | None = None):
        self.desktop = desktop
        self.guard = guard
        self.settle = settle
        self.on_step = on_step
        self.steps: list[Step] = []
        self.pending: list[str] = []  # 次のスクリーンショットまでに実行した行動

    @property
    def environment(self):
        return "linux"

    @property
    def dimensions(self):
        return (self.desktop.width, self.desktop.height)

    async def _check(self, action: dict) -> None:
        if self.guard and (reason := await self.guard(action)):
            raise ActionRefused(reason)

    async def screenshot(self) -> str:
        await asyncio.sleep(self.settle)  # 画面の更新を待ってから撮る（撮るのが早いと、古い画面を見て同じ操作を繰り返す）
        png = await self.desktop.screenshot()
        step = Step(len(self.steps) + 1, self.pending or ["screenshot()"], png)
        self.steps.append(step)
        self.pending = []
        if self.on_step:
            self.on_step(step)
        return base64.b64encode(png).decode()

    async def click(self, x, y, button, *, keys=None):
        await self._check({"type": "click", "x": x, "y": y})
        self.pending.append(f"click({x}, {y}{', ' + button if button != 'left' else ''})")
        await self.desktop.click(x, y, button, keys)

    async def double_click(self, x, y, *, keys=None):
        await self._check({"type": "double_click", "x": x, "y": y})
        self.pending.append(f"double_click({x}, {y})")
        await self.desktop.double_click(x, y, keys)

    async def scroll(self, x, y, scroll_x, scroll_y, *, keys=None):
        self.pending.append(f"scroll({x}, {y}, dy={scroll_y})")
        await self.desktop.scroll(x, y, scroll_x, scroll_y)

    async def type(self, text):
        self.pending.append(f"type({text!r})")
        await self.desktop.type(text)

    async def wait(self):
        self.pending.append("wait()")
        await self.desktop.wait()

    async def move(self, x, y, *, keys=None):
        self.pending.append(f"move({x}, {y})")
        await self.desktop.move(x, y)

    async def keypress(self, keys):
        await self._check({"type": "keypress", "keys": keys})
        self.pending.append("keypress(" + "+".join(keys) + ")")
        await self.desktop.keypress(keys)

    async def drag(self, path, *, keys=None):
        await self._check({"type": "drag", "path": [{"x": x, "y": y} for x, y in path]})
        self.pending.append(f"drag({path[0]} → {path[-1]})")
        await self.desktop.drag(path)


async def run_cu_agent(task: str, computer: SdkDesktop, *, model: str = DEFAULT_MODEL,
                       instructions: str | None = None, max_turns: int = 30, on_safety_check=None,
                       previous_response_id: str | None = None):
    """computer tool の Agent を作って実行する。(Agents SDK の RunResult, Summary) を返す。

    続きを依頼するときは、previous_response_id に前回の result.last_response_id を渡す。
    """
    agent = Agent(name="経費アシスタント", model=model, instructions=instructions,
                  tools=[ComputerTool(computer=computer, on_safety_check=on_safety_check)])
    started, first_step = time.perf_counter(), len(computer.steps)
    result = await Runner.run(agent, task, max_turns=max_turns, previous_response_id=previous_response_id)
    usage = result.context_wrapper.usage
    return result, Summary(result.final_output, computer.steps[first_step:], usage.requests,
                           usage.input_tokens, usage.output_tokens, time.perf_counter() - started)
