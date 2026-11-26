"""OpenAI API を呼ばない回帰テスト。

偽の仮想デスクトップ（操作を記録するだけ）で、Agents SDK 用の AsyncComputer、LangChain 用の Tool、ガードを確かめる。
仮想デスクトップを使うテストは Docker とイメージ（ai-agent-seminar-desktop:17）が必要（ない場合はスキップ）。

    python -m pytest tests
"""

from __future__ import annotations

import base64
import subprocess

import pytest

from computer_use_agent import (
    A11yTools,
    ActionRefused,
    DesktopComputer,
    DesktopGuard,
    SdkDesktop,
    approve_all,
    deny_all,
)
from computer_use_agent.computers import xdotool_key
from computer_use_agent.desktop import IMAGE, list_files, read_file, start_desktop, stop_desktop, wait_until_ready
from computer_use_agent.guard import key_combo

PNG = b"\x89PNG fake"


class FakeDesktop:
    """操作を記録し、AT-SPI と xdotool の代わりに決めた要素とウィンドウ名を返す。"""

    width, height = 1280, 800

    def __init__(self, element=None, window="経費一覧.csv - Mousepad", elements=None):
        self.calls: list[tuple] = []
        self.element, self.window = element, window
        self.elements = elements or {}

    def __getattr__(self, name):  # click / type / keypress などを記録する
        async def record(*args):
            self.calls.append((name, *args))
        return record

    async def screenshot(self):
        return PNG

    async def element_at(self, x, y):
        return {"element": self.element, "window": self.window}

    async def a11y_snapshot(self):
        return {"text": "- text [ref=e1]", "elements": self.elements}

    async def exec(self, *args):
        return self.window.encode()  # xdotool getactivewindow getwindowname の代わり


# --- キー名 ------------------------------------------------------------------------


def test_key_names():
    assert xdotool_key("ENTER") == "Return"
    assert xdotool_key("CTRL") == "ctrl"
    assert xdotool_key("A") == "a"
    assert key_combo(["control", "s"]) == "CTRL+S"


# --- ガード ------------------------------------------------------------------------


async def test_guard_checks_element_at_click_point():
    desktop = FakeDesktop(element={"role": "menu item", "name": "保存(S)"})
    guard = DesktopGuard(desktop, deny_all)
    reason = await guard({"type": "click", "x": 10, "y": 10})
    assert reason and "保存(S)" in reason
    desktop.element = {"role": "menu", "name": "ファイル(F)"}
    assert await guard({"type": "click", "x": 10, "y": 10}) is None


async def test_guard_checks_keys_by_window():
    desktop = FakeDesktop(window="受信 - Thunar")
    guard = DesktopGuard(desktop, deny_all)
    assert await guard({"type": "keypress", "keys": ["CTRL", "V"]})  # Thunar では移動になる
    assert await guard({"type": "keypress", "keys": ["CTRL", "S"]})  # 保存はどのウィンドウでも
    desktop.window = "経費一覧.csv - Mousepad"
    assert await guard({"type": "keypress", "keys": ["CTRL", "V"]}) is None  # エディタでは貼り付け
    assert await DesktopGuard(desktop, approve_all)({"type": "keypress", "keys": ["CTRL", "S"]}) is None


# --- スクリーンショット方式（Agents SDK の AsyncComputer） --------------------------


async def test_sdk_desktop_records_steps():
    desktop = FakeDesktop()
    computer = SdkDesktop(desktop, settle=0)
    await computer.click(10, 20, "left")
    await computer.type("こんにちは")
    image = await computer.screenshot()
    assert base64.b64decode(image) == PNG  # SDK には base64 の文字列で渡す
    assert ("click", 10, 20, "left", None) in desktop.calls and ("type", "こんにちは") in desktop.calls
    assert computer.steps[0].actions == ["click(10, 20)", "type('こんにちは')"]


async def test_sdk_desktop_guard_raises_before_executing():
    desktop = FakeDesktop()
    computer = SdkDesktop(desktop, guard=DesktopGuard(desktop, deny_all), settle=0)
    with pytest.raises(ActionRefused):
        await computer.keypress(["CTRL", "S"])
    assert not any(call[0] == "keypress" for call in desktop.calls)


# --- アクセシビリティツリー方式（LangChain の Tool） ---------------------------------


def a11y_tools(desktop, guard=None) -> dict:
    return {t.name: t for t in A11yTools(desktop, guard=guard, settle=0).tools}


async def test_a11y_tools_click_element_center():
    desktop = FakeDesktop(elements={"e1": {"role": "button", "name": "OK", "x": 100, "y": 200,
                                           "width": 40, "height": 20, "window": "お知らせ"}})
    tools = a11y_tools(desktop)
    assert "現在の画面の要素" in await tools["read_screen"].ainvoke({})
    assert (await tools["click"].ainvoke({"ref": "e1"})).startswith("OK")
    assert ("click", 120, 210, "left") in desktop.calls  # 要素の中心を押す
    assert (await tools["click"].ainvoke({"ref": "e9"})).startswith("失敗")  # アクセシビリティツリーにない参照はモデルに伝える


async def test_a11y_tools_guard_refuses():
    desktop = FakeDesktop(elements={"e1": {"role": "menu item", "name": "保存(S)", "x": 0, "y": 0,
                                           "width": 10, "height": 10, "window": "Mousepad"}})
    tools = a11y_tools(desktop, guard=DesktopGuard(desktop, deny_all).check_tool)
    await tools["read_screen"].ainvoke({})
    assert (await tools["click"].ainvoke({"ref": "e1"})).startswith("実行していない")
    assert (await tools["press_key"].ainvoke({"keys": ["CTRL", "S"]})).startswith("実行していない")
    assert not any(call[0] in ("click", "keypress") for call in desktop.calls)


# --- 仮想デスクトップ（Docker とイメージが必要） --------------------------------------


def image_available() -> bool:
    try:
        return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, timeout=20).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
async def desktop():
    if not image_available():
        pytest.skip(f"Docker か、イメージ {IMAGE} がない")
    start_desktop(name="ai-agent-seminar-desktop-test")
    computer = DesktopComputer("ai-agent-seminar-desktop-test")
    try:
        await wait_until_ready(computer)
        yield computer
    finally:
        stop_desktop(name="ai-agent-seminar-desktop-test")


async def test_desktop_observe_and_operate(desktop):
    assert (await desktop.screenshot()).startswith(b"\x89PNG")
    snapshot = await desktop.a11y_snapshot()
    assert "東京メトロ" in snapshot["text"]  # エディタの中身（経費一覧.csv）が読める
    receipt = next(e for e in snapshot["elements"].values() if e["name"].startswith("領収書_"))
    found = await desktop.element_at(receipt["x"] + 5, receipt["y"] + 5)
    assert found["element"]["name"] == receipt["name"] and "Thunar" in found["window"]

    editor = next(e for e in snapshot["elements"].values() if e["role"] == "text" and "Mousepad" in e["window"])
    await desktop.click(editor["x"] + 300, editor["y"] + 400)
    await desktop.keypress(["CTRL", "END"])
    await desktop.type("テスト")
    await desktop.keypress(["CTRL", "S"])
    await desktop.wait(1)
    assert (await read_file(desktop, "経費一覧.csv")).endswith("テスト")
    assert await list_files(desktop, "受信") == ["領収書_ビジネスホテル港南.txt"]
