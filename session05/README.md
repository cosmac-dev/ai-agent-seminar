# 第5回: Memory Management

## 前提条件

1. Git
2. 実行環境（いずれか）
   - ローカルの Python 3.10 以上 ＋ Jupyter（または **VS Code** Jupyter 拡張機能）
   - **Dev Containers**（Docker 利用。ローカル環境を汚したくない場合）
   - **Google Colab**

## 事前準備

### リポジトリのクローン

ローカルにリポジトリを取得

```bash
git clone https://github.com/cosmac-dev/ai-agent-seminar.git
cd ai-agent-seminar/session05
```

> 既にリポジトリをクローン済みの場合は、最新の状態に更新
>
> ```bash
> cd ai-agent-seminar
> git pull
> ```

### LangSmithのアカウント作成（任意）

> LangGraphサーバーのWeb UIを使用する場合に使用する

1. <https://smith.langchain.com/>にアクセスしてSign Up
2. ブラウザでログインしておく

## Notebook

- [`session05_memory.ipynb`](session05_memory.ipynb)

## パッケージ: `mnemonic-agent`

`src/mnemonic_agent` は、Notebookで扱った短期記憶と長期記憶を搭載した AI エージェントのパッケージ版。

- **短期記憶**: `session_id`（スレッド）ごとに会話履歴を checkpointer で永続化する。
- **長期記憶**: `user_id` ごとに恒常的な事実を Store へ抽出・検証して保存し、

### ライブラリとして使用

```python
from mnemonic_agent import Agent

agent = Agent()  # 既定で ChatOpenAI と埋め込み付き InMemoryStore を使用

agent.run("覚えて: 私はPythonが好きです", user_id="user-001", session_id="s1")
print(agent.run("私について覚えていることは？", user_id="user-001", session_id="s1"))
print(agent.recall("user-001"))  # 保存済みの長期記憶を一覧
```

### LangGraph Server として起動

1. プロジェクトルートに`.env`ファイルを作成し、`OPENAI_API_KEY`を設定
   ```bash
   cho "OPENAI_API_KEY=sk-..." > .env 
   ```
2. langgraph-cliをインストール
    ```bash
    pip install -e ".[server]"
    ```
3. 起動
    ```bash
    langgraph dev
    # Colabの場合はlanggraph dev --tunnel
    ```
4. ブラウザで<http://127.0.0.1:2024>にアクセス
   > Colabの場合はターミナルに表示されたWeb UIのリンクをクリック

グラフとストア設定は [`langgraph.json`](langgraph.json) で宣言する。長期記憶の
セマンティック検索設定（埋め込みモデル・次元・対象フィールド）は同ファイルの `store.index`
で定義するため、サーバー用エントリポイント（`server.py:make_graph`）は
**checkpointer / store を渡さずに** コンパイル（サーバーが自動注入）。