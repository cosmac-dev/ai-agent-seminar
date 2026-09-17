"""公開ディレクトリを限定したファイル操作 MCP Server。

常駐プロセスとして Streamable HTTP で起動する。

    python3 src/mcp-server/server.py

環境変数で挙動を変えられる。

- MCP_FILES_ROOT: 公開するディレクトリ。既定は workspace
- MCP_TRANSPORT: http（既定）または stdio
"""

import os
import sys
from pathlib import Path

from fastmcp import FastMCP

ROOT = Path(
    os.environ.get('MCP_FILES_ROOT', Path(__file__).parents[2] / 'workspace')
).resolve()
ROOT.mkdir(parents=True, exist_ok=True)

mcp = FastMCP('Managed Files Server')


def _resolve(relative_path: str) -> Path:
    """ROOT の外を指す相対パスを拒否して、解決済みの絶対パスを返す。

    resolve() が `..` と symlink を展開するため、展開後に ROOT 配下か検査する。
    """
    target = (ROOT / relative_path).resolve()
    if target != ROOT and ROOT not in target.parents:
        raise ValueError(f'{relative_path} は公開範囲の外にある')
    return target


@mcp.tool
def list_files() -> list[str]:
    """公開ディレクトリにあるファイルの相対パス一覧を返す。"""
    return sorted(
        str(path.relative_to(ROOT)) for path in ROOT.rglob('*') if path.is_file()
    )


@mcp.tool
def read_file(relative_path: str) -> str:
    """公開ディレクトリ内のテキストファイルを読む。

    Args:
        relative_path: 公開ディレクトリからの相対パス。
    """
    target = _resolve(relative_path)
    if not target.is_file():
        raise ValueError(f'{relative_path} は存在しない')
    return target.read_text(encoding='utf-8')


@mcp.tool
def write_file(relative_path: str, content: str) -> dict:
    """公開ディレクトリ内のテキストファイルへ書き込む。

    Args:
        relative_path: 公開ディレクトリからの相対パス。
        content: 書き込む内容。既存の内容は置き換わる。
    """
    target = _resolve(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
    return {
        'path': str(target.relative_to(ROOT)),
        'bytes_written': len(content.encode('utf-8')),
    }


if __name__ == '__main__':
    # STDIO では標準出力が JSON-RPC の通信路になる。ログは必ず標準エラーへ出す
    print(f'公開ディレクトリ: {ROOT}', file=sys.stderr)

    if os.environ.get('MCP_TRANSPORT', 'http') == 'stdio':
        mcp.run(transport='stdio')
    else:
        mcp.run(transport='http', host='127.0.0.1', port=8000)
