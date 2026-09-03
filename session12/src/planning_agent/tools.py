"""実行部が使う Tool 一式。

第8回で導入した実務 Tool を引き継ぎ、第9回・第10回の HITL とサンドボックス
付き実行部（`executor.make_guarded_agent()`）から利用する。

- Web検索/取得: `web_search` / `fetch_url`（Tavily。`TAVILY_API_KEY` が必要）
- ファイル操作: `WORKSPACE_DIR`（カレントディレクトリ直下 `agent_workspace`）を
  ルートに限定した read/write/copy/move/delete/list/search
- HTTP: requests_get/post/patch/put/delete
- ホスト直実行: `run_command` / `python_repl`

グラフ本体では `run_command` / `python_repl` を除外し、サンドボックス付きの
`shell` Tool だけを実行経路にする。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from langchain_community.tools.file_management import (
    CopyFileTool,
    DeleteFileTool,
    FileSearchTool,
    ListDirectoryTool,
    MoveFileTool,
    ReadFileTool,
    WriteFileTool,
)
from langchain_community.tools.requests.tool import (
    RequestsDeleteTool,
    RequestsGetTool,
    RequestsPatchTool,
    RequestsPostTool,
    RequestsPutTool,
)
from langchain_community.tools.shell.tool import ShellTool
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain_core.tools import BaseTool, tool
from langchain_experimental.utilities import PythonREPL
from langchain_tavily import TavilyExtract, TavilySearch

from .knowledge import DEFAULT_TOP_K, KnowledgeBase

# ファイル操作 Tool のルートディレクトリ（この外は読み書きできない）
WORKSPACE_DIR = Path("agent_workspace").resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# --- Web検索・取得 -----------------------------------------------------------

web_search = TavilySearch(
    name="web_search",
    max_results=3,
    search_depth="basic",
    include_answer=False,
    include_raw_content=False,
)

fetch_url = TavilyExtract(
    name="fetch_url",
    extract_depth="basic",
    include_images=False,
    format="markdown",
    chunks_per_source=1,
)

# --- ファイル操作 -------------------------------------------------------------

write_file = WriteFileTool(root_dir=str(WORKSPACE_DIR))
read_file = ReadFileTool(root_dir=str(WORKSPACE_DIR))
copy_file = CopyFileTool(root_dir=str(WORKSPACE_DIR))
move_file = MoveFileTool(root_dir=str(WORKSPACE_DIR))
file_delete = DeleteFileTool(root_dir=str(WORKSPACE_DIR))
list_directory = ListDirectoryTool(root_dir=str(WORKSPACE_DIR))
file_search = FileSearchTool(root_dir=str(WORKSPACE_DIR))

# --- HTTP ---------------------------------------------------------------------

_requests_wrapper = TextRequestsWrapper(
    headers={"User-Agent": "ai-agent-seminar-session09/1.0"}
)
requests_get = RequestsGetTool(
    requests_wrapper=_requests_wrapper, allow_dangerous_requests=True
)
requests_post = RequestsPostTool(
    requests_wrapper=_requests_wrapper, allow_dangerous_requests=True
)
requests_patch = RequestsPatchTool(
    requests_wrapper=_requests_wrapper, allow_dangerous_requests=True
)
requests_put = RequestsPutTool(
    requests_wrapper=_requests_wrapper, allow_dangerous_requests=True
)
requests_delete = RequestsDeleteTool(
    requests_wrapper=_requests_wrapper, allow_dangerous_requests=True
)

# --- コマンド・コード実行 -------------------------------------------------------

run_command = ShellTool(
    name="run_command",
    ask_human_input=False,
)

_python_repl = PythonREPL()


@tool
def python_repl(code: str) -> str:
    """Pythonコードを実行する。結果として確認したい値はprintで出力すること。"""
    return _python_repl.run(code)


# --- Knowledge Retrieval -------------------------------------------------------
def make_search_tool(knowledge_base: KnowledgeBase, *, top_k: int = DEFAULT_TOP_K):
    """知識ベースに束縛された RAG 検索ツールを生成する。"""

    @tool(parse_docstring=True)
    def search_knowledge_base(query: str) -> str:
        """取り込み済みドキュメント（知識ベース）をRAG検索し、関連するチャンクを返す。

        ドキュメントの内容に基づいて答えるべき質問で使う。
        検索結果が質問と関係ない場合は、無理に答えず「分からない」と判断する。

        Args:
            query: 検索したい内容。例 'リモートワークの上限日数'。
        """
        try:
            return knowledge_base.search_text(query, top_k=top_k)
        except Exception as exc:  # noqa: BLE001 - ツールの観測として返す
            return f"知識ベース検索エラー: {exc}"

    return search_knowledge_base


DEFAULT_TOOLS = [
    list_directory,
    read_file,
    write_file,
    copy_file,
    move_file,
    file_search,
    file_delete,
    web_search,
    fetch_url,
    requests_get,
    requests_post,
    requests_patch,
    requests_put,
    requests_delete,
    run_command,
    python_repl,
]

HOST_EXECUTION_TOOL_NAMES = {"run_command", "python_repl"}


def without_host_execution_tools(tools: Iterable[BaseTool]) -> list[BaseTool]:
    """ホスト直実行 Tool を除いた Tool 一覧を返す。"""
    return [tool for tool in tools if tool.name not in HOST_EXECUTION_TOOL_NAMES]
