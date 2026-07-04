from __future__ import annotations

import ast
import datetime as _dt
import operator

from langchain_core.tools import tool

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
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
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
        return str(_safe_eval(ast.parse(expression, mode="eval")))
    except Exception as exc:  # noqa: BLE001 - ハンズオンでは観測として返す
        return f"計算エラー: {exc}"


@tool
def current_datetime() -> str:
    """現在のローカル日時をISO形式で返す。"""
    return _dt.datetime.now().isoformat(timespec="seconds")


DEFAULT_TOOLS = [calculator, current_datetime]
