"""行動を実行する前の確認（ガードレール）。

- `DesktopGuard`: 押す要素やキーを AT-SPI で調べ、取り消しにくい操作（保存・削除・移動）の前で人に確認する。
- `ActionRefused`: スクリーンショット方式で、人が操作を許可しなかったときに投げる例外。
- `ask_in_terminal` / `deny_all` / `approve_all`: 確認の応じ方（人に聞く / すべて断る / すべて許す）。
"""

from __future__ import annotations

from typing import Awaitable, Callable

from .computers import DesktopComputer

# 確認する内容（文）を受け取り、許可なら True を返す
Approver = Callable[[str], Awaitable[bool]]


class ActionRefused(Exception):
    """人が操作を許可しなかった。Agents SDK の Runner.run から、この例外がそのまま出てくる。"""


async def ask_in_terminal(message: str) -> bool:
    """input() で人に聞く。Notebook でも入力欄が出る。"""
    return input(f"{message}\n実行してよいですか？ [y/N]: ").strip().lower() == "y"


async def deny_all(message: str) -> bool:
    print(f"[確認] {message} → 拒否")
    return False


async def approve_all(message: str) -> bool:
    print(f"[確認] {message} → 許可")
    return True


# 押す前に確認する要素の名前（部分一致）。メニューの「保存(S)」、右クリックメニューの「ゴミ箱に移動(V)」など
RISKY_LABELS = ("保存", "削除", "ゴミ箱", "貼り付け", "ここに移動")
# 押す前に確認するキー。値は、そのキーが危ないウィンドウの名前（部分一致。空文字ならどのウィンドウでも）
RISKY_KEYS = {"CTRL+S": "", "DELETE": "Thunar", "SHIFT+DELETE": "Thunar", "CTRL+V": "Thunar"}


def key_combo(keys: list[str]) -> str:
    """["ctrl", "s"] → "CTRL+S"。修飾キーの名前の違い（CONTROL など）をそろえる。"""
    aliases = {"CONTROL": "CTRL", "DEL": "DELETE"}
    return "+".join(aliases.get(k.upper(), k.upper()) for k in keys)


class DesktopGuard:
    """取り消しにくい操作の前で、人に確認する。

    computer tool の行動（座標）は、座標にある要素を AT-SPI で調べてから判断する。
    アクセシビリティツリーのエージェントの行動（ref）は、要素がわかっているのでそのまま判断する。
    """

    def __init__(self, computer: DesktopComputer, approver: Approver,
                 risky_labels=RISKY_LABELS, risky_keys=None):
        self.computer = computer
        self.approver = approver
        self.risky_labels = risky_labels
        self.risky_keys = RISKY_KEYS if risky_keys is None else risky_keys

    async def check_element(self, element: dict | None, window: str, verb: str) -> str | None:
        name = (element or {}).get("name", "")
        if not any(label in name for label in self.risky_labels):
            return None
        if await self.approver(f"「{name}」（{window}）を{verb}"):
            return None
        return f"人が「{name}」の操作を許可しなかった"

    async def check_keys(self, keys: list[str]) -> str | None:
        combo = key_combo(keys)
        if combo not in self.risky_keys:
            return None
        window = (await self.computer.exec("xdotool", "getactivewindow", "getwindowname")).decode().strip()
        if self.risky_keys[combo] not in window:
            return None
        if await self.approver(f"{combo} を「{window}」で押す"):
            return None
        return f"人が {combo} の操作を許可しなかった"

    async def __call__(self, action: dict, computer=None) -> str | None:
        """computer tool の行動を調べる（cu_agent.SdkDesktop の guard に渡す）。止めるなら理由を返す。"""
        match action["type"]:
            case "click" | "double_click":
                found = await self.computer.element_at(action["x"], action["y"])
                return await self.check_element(found["element"], found["window"], "押す")
            case "drag":
                # ファイルを別のフォルダへ落とすと移動になる。落とす先を調べて確認する
                (x0, y0), (x1, y1) = (action["path"][0]["x"], action["path"][0]["y"]), \
                                     (action["path"][-1]["x"], action["path"][-1]["y"])
                source = (await self.computer.element_at(x0, y0))["element"] or {}
                found = await self.computer.element_at(x1, y1)
                target = (found["element"] or {}).get("name", "")
                if source.get("role") == "table cell" and source.get("name"):
                    if await self.approver(f"「{source['name']}」を「{target}」（{found['window']}）へドラッグする"):
                        return None
                    return "人がドラッグによる移動を許可しなかった"
                return None
            case "keypress":
                return await self.check_keys(action["keys"])
            case _:
                return None

    async def check_tool(self, name: str, args: dict, element: dict | None, window: str = "") -> str | None:
        """アクセシビリティツリー方式の Tool 呼び出しを調べる（a11y_agent.make_tools の guard に渡す）。"""
        if name in ("click", "double_click"):
            return await self.check_element(element, window, "押す")
        if name == "press_key":
            return await self.check_keys(args["keys"])
        return None
