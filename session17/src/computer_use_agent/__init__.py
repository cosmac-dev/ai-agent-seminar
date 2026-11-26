"""第17回 Computer Use の完成版実装。

- computers: 仮想デスクトップの観測と操作（import でスクリーンショット、xdotool で入力、AT-SPI でアクセシビリティツリー）
- cu_agent: スクリーンショット方式（computer tool × OpenAI Agents SDK）
- a11y_agent: アクセシビリティツリー方式（AT-SPI × LangChain の create_agent）
- guard: 取り消しにくい操作の前の確認
- desktop: 仮想デスクトップのコンテナの起動・停止と、結果の確認
"""

from .a11y_agent import A11yTools, run_a11y_agent
from .computers import Computer, DesktopComputer
from .cu_agent import SdkDesktop, run_cu_agent
from .guard import ActionRefused, DesktopGuard, approve_all, ask_in_terminal, deny_all
from .steps import Step, Summary

__all__ = [
    "A11yTools",
    "ActionRefused",
    "Computer",
    "DesktopComputer",
    "DesktopGuard",
    "SdkDesktop",
    "Step",
    "Summary",
    "approve_all",
    "ask_in_terminal",
    "deny_all",
    "run_a11y_agent",
    "run_cu_agent",
]
