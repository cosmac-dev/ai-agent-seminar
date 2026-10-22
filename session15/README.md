# 第15回: マルチエージェント

## 前提条件

1. Git
2. 実行環境（いずれか）
   - ローカルの Python 3.10 以上 ＋ Jupyter（または **VS Code** Jupyter 拡張機能）
   - **Dev Containers**（Docker 利用）
   - **Google Colab**
3. OpenAI の API キー（`OPENAI_API_KEY`）

本回では、LangChain の `create_agent` で親エージェントと担当のサブエージェントを作る。
親エージェントがサブエージェントを Tool として並行に呼び出し、全結果が揃ってから出典付きで集約する。
Notebook の実行とデモは OpenAI のモデルを呼び出すため、利用料金が発生する。

## 事前準備

### リポジトリのクローン

```bash
git clone https://github.com/cosmac-dev/ai-agent-seminar.git
cd ai-agent-seminar/session15
```

既にクローン済みの場合は、ローカルの変更を保全して最新の教材に更新し、本回のディレクトリへ移動する。

### Notebook の実行

- ローカル: Python 3.10 以上の Jupyter カーネルを選び、上から順にセルを実行する。
- Dev Container: VS Codeでリポジトリを開き、**Dev Containers: Reopen in Container** から `ai-agent-seminar-session15` を選ぶ。[専用設定](../.devcontainer/session15/devcontainer.json)がPythonとNotebook用カーネルを用意し、完成版パッケージを導入する。
- Colab: Notebook 冒頭の **Open in Colab** から開く。Notebook は単独で動作する。

API キーは Notebook の入力欄、環境変数 `OPENAI_API_KEY`、または Colab Secret で設定する。キーをコード・出力・Git に保存しない。

Notebook 内ではトップレベルの `await` を使用する。`asyncio.run` は通常の Python スクリプトで使用する。

## Notebook

- [`session15_multi_agent.ipynb`](session15_multi_agent.ipynb)

## パッケージ: `cooperative-workflow`

`src/cooperative_workflow` は Notebook の完成版実装。別セッションを import しない。
依存パッケージは `langchain`、`langgraph`、`langchain-openai`。

### ライブラリとして使用

本回のディレクトリでインストールする。

```bash
python -m pip install -e .
```

```python
import asyncio
from langchain_openai import ChatOpenAI
from cooperative_workflow import run_supervisor

model = ChatOpenAI(model="gpt-5.4-mini")
result = asyncio.run(run_supervisor(model, "この製品の機能、導入条件、利用者の要望を確認したい。"))
print(result.report)
for event in result.events:
    print(event.elapsed, event.actor, event.phase)
```

Notebook からライブラリを使う場合は `result = await run_supervisor(model, ...)` とする。
完成版デモは `python -m cooperative_workflow` で実行できる。引数でモデル名を指定できる（既定は `gpt-5.4-mini`）。

