"""実行の記録（途中経過と統計）。2つの方式で同じ形にして、比べられるようにする。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    index: int
    actions: list[str]  # 実行した行動（表示用の文字列）
    screenshot: bytes   # 実行後の画面


@dataclass
class Summary:
    final_text: str
    steps: list[Step] = field(default_factory=list)
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    elapsed: float = 0.0
