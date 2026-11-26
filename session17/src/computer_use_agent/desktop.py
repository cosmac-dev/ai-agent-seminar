"""デスクトップ環境のコンテナを起動・停止する。

コンテナは外部ネットワークに出られない（--network none）、ホストのファイルをマウントしない、
権限を持たない（--cap-drop ALL、no-new-privileges）設定で動かす。
エージェントが誤った操作や画面上の指示に従っても、影響はコンテナの中にとどまる。
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from .computers import DesktopComputer

IMAGE = "ai-agent-seminar-desktop:17"
CONTAINER = "ai-agent-seminar-desktop"
SESSION_DIR = Path(__file__).resolve().parents[2]


def docker_available() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_image(context: Path = SESSION_DIR, image: str = IMAGE) -> None:
    """desktop/Dockerfile からイメージを作る（初回は数分かかる）。"""
    subprocess.run(["docker", "build", "-f", str(context / "desktop" / "Dockerfile"), "-t", image, str(context)],
                   check=True)


def start_desktop(image: str = IMAGE, name: str = CONTAINER) -> None:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    subprocess.run([
        "docker", "run", "-d", "--rm", "--name", name,
        "--network", "none",                       # 外部ネットワークに出られない
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "512", "--memory", "2g", "--shm-size", "512m",
        image,
    ], check=True, capture_output=True)


async def wait_until_ready(computer: DesktopComputer, timeout: float = 60) -> None:
    """デスクトップと、Thunar・Mousepad の表示を待つ。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            await computer.exec("test", "-f", "/tmp/desktop-ready")
            await asyncio.sleep(2)  # ウィンドウの描画を待つ
            return
        except RuntimeError:
            await asyncio.sleep(1)
    raise TimeoutError("デスクトップが起動しなかった")


# --- 結果の確認と、仕掛けの用意（エージェントではなく、このコードが直接行う） ---

HOME = "/home/seminar"


async def read_file(computer: DesktopComputer, path: str) -> str:
    """コンテナの中のファイルを読む。path はホームからの相対パス。"""
    return (await computer.exec("cat", f"{HOME}/{path}")).decode()


async def list_files(computer: DesktopComputer, path: str) -> list[str]:
    """コンテナの中のフォルダにあるファイルの名前（隠しファイルを除く）。"""
    out = (await computer.exec("ls", "-1", f"{HOME}/{path}")).decode()
    return [line for line in out.splitlines() if line]


async def show_dialog(computer: DesktopComputer, text: str, title: str = "お知らせ", delay: float = 0) -> None:
    """delay 秒後に、デスクトップにダイアログを出す（第6節で、作業中に割り込むポップアップに使う）。"""
    # デスクトップと同じ D-Bus のセッションで起動する（start.sh が書き出したバスの場所を使う）。
    # 外から起動したウィンドウはウィンドウマネージャが後ろに回すことがあるため、実際のポップアップのように前面に出す
    script = ('export DBUS_SESSION_BUS_ADDRESS="$(cat /tmp/dbus-session-address)"; '
              f'sleep {delay}; notice "$1" "$2" & '
              'xdotool search --sync --onlyvisible --name "^$1$" windowactivate; wait')
    await computer.exec("bash", "-c", f"({script}) >/dev/null 2>&1 &", "dialog", title, text)


def stop_desktop(name: str = CONTAINER) -> None:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
