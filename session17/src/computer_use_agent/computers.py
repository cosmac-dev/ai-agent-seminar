"""Docker コンテナの仮想デスクトップ（Xvfb）を観測し、操作する。

- 画面を撮る: ImageMagick の `import`
- 入力する: `xdotool`（X11 に擬似的なマウス・キーボードの入力を送る。Windows の SendInput にあたる）
- 画面の要素を読む: AT-SPI（`a11y` コマンド。Windows の UI Automation にあたる）

Agents SDK の AsyncComputer（cu_agent.SdkDesktop）も LangChain の Tool（a11y_agent.A11yTools）も、このクラスのメソッドで画面を操作する。
"""

from __future__ import annotations

import asyncio
import json
from typing import Protocol

# --- キー名の変換表 -------------------------------------------------------------
# モデルは "CTRL" "ENTER" のような大文字のキー名を返す。実行側が受け付ける名前に直す。

XDOTOOL_KEYS = {
    "ENTER": "Return", "RETURN": "Return", "ESC": "Escape", "ESCAPE": "Escape", "TAB": "Tab",
    "SPACE": "space", "BACKSPACE": "BackSpace", "DELETE": "Delete", "DEL": "Delete",
    "HOME": "Home", "END": "End", "PAGEUP": "Page_Up", "PAGEDOWN": "Page_Down",
    "UP": "Up", "DOWN": "Down", "LEFT": "Left", "RIGHT": "Right",
    "ARROWUP": "Up", "ARROWDOWN": "Down", "ARROWLEFT": "Left", "ARROWRIGHT": "Right",
    "CTRL": "ctrl", "CONTROL": "ctrl", "SHIFT": "shift", "ALT": "alt", "OPTION": "alt",
    "META": "super", "CMD": "super", "COMMAND": "super", "SUPER": "super",
}

XDOTOOL_BUTTONS = {"left": 1, "wheel": 2, "middle": 2, "right": 3, "back": 8, "forward": 9}


def xdotool_key(key: str) -> str:
    return XDOTOOL_KEYS.get(key.upper(), key.lower() if len(key) == 1 else key)


class Computer(Protocol):
    """操作対象が備えるメソッド。座標はスクリーンショットのピクセルで数える。"""

    width: int
    height: int

    async def screenshot(self) -> bytes: ...
    async def click(self, x: int, y: int, button: str = "left", keys: list[str] | None = None) -> None: ...
    async def double_click(self, x: int, y: int, keys: list[str] | None = None) -> None: ...
    async def move(self, x: int, y: int) -> None: ...
    async def drag(self, path: list[tuple[int, int]]) -> None: ...
    async def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None: ...
    async def type(self, text: str) -> None: ...
    async def keypress(self, keys: list[str]) -> None: ...
    async def wait(self, seconds: float = 2.0) -> None: ...


# --- デスクトップ（Docker コンテナの Xvfb） ------------------------------------------


class DesktopComputer:
    """コンテナ内の仮想ディスプレイを `docker exec` 経由で操作する。

    スクリーンショットは ImageMagick の `import`、マウスとキーボードは `xdotool`、
    画面の要素は AT-SPI（コンテナの中の `a11y` コマンド）で扱う。ホスト側の画面や入力デバイスには一切触れない。
    """

    def __init__(self, container: str, display: str = ":99", width: int = 1280, height: int = 800):
        self.container = container
        self.display = display
        self.width = width
        self.height = height

    async def exec(self, *args: str | int) -> bytes:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "--env", f"DISPLAY={self.display}", self.container, *map(str, args),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"{args[0]} が失敗した: {stderr.decode(errors='replace').strip()}")
        return stdout

    async def xdotool(self, *args: str | int) -> None:
        await self.exec("xdotool", *args)

    async def screenshot(self) -> bytes:
        return await self.exec("import", "-window", "root", "png:-")

    def _modifiers(self, keys: list[str] | None, action: str) -> list[str]:
        return [part for key in keys or [] for part in (action, xdotool_key(key))]

    async def click(self, x, y, button="left", keys=None):
        await self.xdotool("mousemove", x, y, *self._modifiers(keys, "keydown"),
                           "click", XDOTOOL_BUTTONS[button], *self._modifiers(keys, "keyup"))

    async def double_click(self, x, y, keys=None):
        await self.xdotool("mousemove", x, y, *self._modifiers(keys, "keydown"),
                           "click", "--repeat", 2, 1, *self._modifiers(keys, "keyup"))

    async def move(self, x, y):
        await self.xdotool("mousemove", x, y)

    async def drag(self, path):
        (x0, y0), *rest = path
        args: list[str | int] = ["mousemove", x0, y0, "mousedown", 1]
        for x, y in rest:
            args += ["mousemove", x, y]
        await self.xdotool(*args, "mouseup", 1)

    async def scroll(self, x, y, scroll_x, scroll_y):
        # ホイール1目盛りをおよそ 100px とみなす。上下は 4/5、左右は 6/7 のボタン
        clicks: list[int] = []
        for delta, negative, positive in ((scroll_y, 4, 5), (scroll_x, 6, 7)):
            if delta:
                clicks += [negative if delta < 0 else positive] * max(1, abs(round(delta / 100)))
        args: list[str | int] = ["mousemove", x, y]
        for button in clicks:
            args += ["click", button]
        await self.xdotool(*args)

    async def type(self, text):
        # 日本語も xdotool が一時的にキー割り当てを作って入力する
        await self.xdotool("type", "--delay", 20, "--", text)

    async def keypress(self, keys):
        await self.xdotool("key", "--clearmodifiers", "+".join(xdotool_key(k) for k in keys))

    async def wait(self, seconds=2.0):
        await asyncio.sleep(seconds)

    # --- 画面の要素（AT-SPI） ---

    async def a11y(self, *args: str | int) -> dict:
        """コンテナの中の a11y コマンドを実行し、出力の JSON を読む。"""
        for _ in range(3):
            out = await self.exec("a11y", *args)
            if out.strip():
                return json.loads(out)
            await asyncio.sleep(0.5)  # 出力が空のことがあった（原因は未確認）。少し待って読み直す
        raise RuntimeError(f"a11y {' '.join(map(str, args))} の出力が空だった")

    async def a11y_snapshot(self) -> dict:
        """表示されているアクセシビリティツリー。{"text": ツリーのテキスト, "elements": {ref: 役割・名前・位置}} を返す。"""
        return await self.a11y("snapshot")

    async def element_at(self, x: int, y: int) -> dict:
        """座標にある要素と、それを含むウィンドウ。{"element": {...} または None, "window": 名前} を返す。"""
        return await self.a11y("at", x, y)
