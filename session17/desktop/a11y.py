#!/usr/bin/env python3
"""AT-SPI で画面の要素を読み、JSON で出力する（仮想デスクトップの中で docker exec から実行する）。

    a11y snapshot   画面に表示されているアクセシビリティツリー。操作できる要素には ref（e1, e2, ...）を付ける
    a11y at X Y     座標 (X, Y) にある要素と、それを含むウィンドウ

AT-SPI は Linux のアクセシビリティの仕組み（Windows の UI Automation にあたる）。
アプリが公開する要素の役割・名前・状態・画面上の位置を読める。
"""

import json
import sys

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

# アクセシビリティツリーに出さないアプリ（デスクトップの部品）
SKIP_APPS = {"xfce4-session", "xfwm4", "xfsettingsd", "xfdesktop", "wrapper-2.0", "xfce4-notifyd"}
# ref を付ける（操作の対象になる）役割
TARGET_ROLES = {
    "button", "push button", "toggle button", "menu", "menu item", "check menu item", "radio menu item",
    "check box", "radio button", "combo box", "text", "entry", "password text", "table cell",
    "list item", "page tab", "link", "spin button", "slider", "tree item",
}
# 名前がなくても出す役割（入力欄は名前を持たないことが多い）。ほかの役割は、名前がなければ入れ物として扱う
UNNAMED_ROLES = {"text", "entry", "password text"}
# ref は付けないが、まとまりの見出しとして出す役割
HEADING_ROLES = {"frame", "dialog", "alert", "window", "label", "status bar", "heading"}
MAX_TEXT = 3000  # テキストの中身はこの文字数まで


def extents(acc):
    e = acc.get_extents(Atspi.CoordType.SCREEN)
    return e.x, e.y, e.width, e.height


def text_of(acc) -> str | None:
    try:
        count = Atspi.Text.get_character_count(acc)
    except Exception:
        return None
    text = Atspi.Text.get_text(acc, 0, min(count, MAX_TEXT))
    return text + ("…（以下省略）" if count > MAX_TEXT else "")


def visible_nodes():
    """表示されている要素を (深さ, 要素, 役割, 名前, 位置) の順に返す。名前のない入れ物は飛ばして子を上げる。"""
    desktop = Atspi.get_desktop(0)
    seen = set()

    def walk(acc, depth):
        try:
            states = acc.get_state_set()
            # 最小化したウィンドウも SHOWING のままなので、ICONIFIED も見る（タスクバーのボタンは残る）
            if not states.contains(Atspi.StateType.SHOWING) or states.contains(Atspi.StateType.ICONIFIED):
                return
            role, name = acc.get_role_name(), (acc.get_name() or "").strip()
            x, y, w, h = extents(acc)
            shown = w > 0 and h > 0 and (name or role in UNNAMED_ROLES) and (role in TARGET_ROLES or role in HEADING_ROLES)
            key = (role, name, x, y, w, h)
            if shown and key not in seen:
                seen.add(key)
                yield depth, acc, role, name, (x, y, w, h), states
                depth += 1
            for i in range(acc.get_child_count()):
                yield from walk(acc.get_child_at_index(i), depth)
        except Exception:  # 応答しない要素や、走査中に消えた要素は飛ばす
            return

    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app is None or (app.get_name() or "") in SKIP_APPS:
            continue
        for j in range(app.get_child_count()):
            yield from walk(app.get_child_at_index(j), 0)


def snapshot() -> dict:
    lines, elements = [], {}
    window = ""
    for depth, acc, role, name, (x, y, w, h), states in visible_nodes():
        if depth == 0:
            window = name if role in HEADING_ROLES else ""
        line = "  " * depth + f"- {role}"
        if name:
            line += f' "{name}"'
        if role in TARGET_ROLES:
            ref = f"e{len(elements) + 1}"
            elements[ref] = {"role": role, "name": name, "x": x, "y": y, "width": w, "height": h, "window": window}
            line += f" [ref={ref}]"
        for state, label in ((Atspi.StateType.FOCUSED, "focused"), (Atspi.StateType.SELECTED, "selected"),
                             (Atspi.StateType.CHECKED, "checked")):
            if states.contains(state):
                line += f" [{label}]"
        if role in ("text", "entry"):
            text = text_of(acc)
            if states.contains(Atspi.StateType.FOCUSED):
                # 入力する位置（カーソル）。文字はここに入るので、モデルが位置を判断できるように出す
                line += f" [caret={Atspi.Text.get_caret_offset(acc)}/{Atspi.Text.get_character_count(acc)}]"
            if text:
                line += ": " + json.dumps(text, ensure_ascii=False)
        lines.append(line)
    return {"text": "\n".join(lines), "elements": elements}


def at(px: int, py: int) -> dict:
    """座標にある要素のうち、いちばん小さいもの（最も内側）と、それを含むウィンドウの名前を返す。"""
    best, window = None, ""
    current_window = ""
    for depth, acc, role, name, (x, y, w, h), _ in visible_nodes():
        if depth == 0:
            current_window = name
        if x <= px < x + w and y <= py < y + h and (role in TARGET_ROLES or role == "label"):
            if best is None or w * h <= best["width"] * best["height"]:
                best = {"role": role, "name": name, "x": x, "y": y, "width": w, "height": h}
                window = current_window
    return {"element": best, "window": window}


def main(argv: list[str]) -> None:
    Atspi.set_timeout(2000, 5000)  # 応答しないアプリで止まらないようにする（ミリ秒）
    if argv[:1] == ["snapshot"]:
        result = snapshot()
    elif argv[:1] == ["at"] and len(argv) == 3:
        result = at(int(argv[1]), int(argv[2]))
    else:
        sys.exit(__doc__)
    json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1:])
