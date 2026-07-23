"""session08 の実務 Tool 一式。

ノートブック（session08_tools.ipynb）で単体確認した Tool を
`DEFAULT_TOOLS` としてまとめる。グラフ側はこのリストを既定で使うため、
利用者が個々の Tool を明示的にインポートする必要はない。

- Web検索/取得: `web_search` / `fetch_url`（Tavily。`TAVILY_API_KEY` が必要）
- ファイル操作: `WORKSPACE_DIR`（カレントディレクトリ直下 `agent_workspace`）を
  ルートに限定した read/write/copy/move/delete/list/search
- HTTP: requests_get/post/patch/put/delete
- コマンド/コード実行: `run_command`（シェル）/ `python_repl`（Python）
"""

from __future__ import annotations

from pathlib import Path

from .knowledge import DEFAULT_TOP_K, KnowledgeBase

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
from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from langchain_tavily import TavilyExtract, TavilySearch

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
    headers={"User-Agent": "ai-agent-seminar-session08/1.0"}
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
    """知識ベースに束縛された RAG 検索ツールを生成する。

    検索対象のドキュメントはハードコードせず、取り込み済みの
    `KnowledgeBase` を実行時に注入する。
    """

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
