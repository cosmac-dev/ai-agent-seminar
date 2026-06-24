from __future__ import annotations

import ast
import datetime as _dt
import operator

from langchain_core.tools import tool

# 安全に評価できる演算のみ許可する（eval は使わない）
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    """AST を再帰的にたどり、許可した数値演算だけを評価する。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("数値以外の定数は使えない。")
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("対応していない演算子。")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("対応していない単項演算子。")
        return op(_safe_eval(node.operand))
    raise ValueError("数式として解釈できない。")


@tool(parse_docstring=True)
def calculator(expression: str) -> str:
    """数式を計算して結果を返す。四則演算・べき乗(**)・括弧に対応。

    Args:
        expression: 計算したい数式の文字列。例 '2 * (3 + 4)'。
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
    except Exception as exc:  # noqa: BLE001 - ツールは失敗を文字列で返す
        return f"計算エラー: {exc}"
    return str(result)


@tool
def current_datetime() -> str:
    """現在のローカル日時を ISO 形式（秒まで）で返す。引数は不要。"""
    return _dt.datetime.now().isoformat(timespec="seconds")


# デモ用の簡易検索（実際の検索 API の代わりに固定回答を返すスタブ）
_FAKE_KNOWLEDGE = {
    "capital of france": "フランスの首都はパリである。",
    "フランスの首都": "フランスの首都はパリである。",
    "tallest mountain": "世界で最も高い山はエベレスト（標高約8,849m）である。",
    "世界一高い山": "世界で最も高い山はエベレスト（標高約8,849m）である。",
}


@tool(parse_docstring=True)
def search_information(query: str) -> str:
    """与えられたトピックの事実情報を返す（デモ用スタブ）。

    'フランスの首都' や '世界一高い山' のような事実質問に使う。

    Args:
        query: 事実を知りたいトピックの文字列。例 'フランスの首都'。
    """
    key = query.lower().strip()
    return _FAKE_KNOWLEDGE.get(
        key,
        f"'{query}' に関する確かな情報は見つからなかった（デモ用スタブのため）。",
    )
