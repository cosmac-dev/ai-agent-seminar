# 第8回: ファイル操作・コマンド実行・Web検索

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
cd ai-agent-seminar/session08
```

> 既にリポジトリをクローン済みの場合は、最新の状態に更新
>
> ```bash
> cd ai-agent-seminar
> git pull
> ```

### Tavilyのアカウント作成と API キー取得

> Web検索（`web_search`）・URL取得（`fetch_url`）ツールの実行に必要

1. <https://app.tavily.com/> にアクセスし、**Sign up** リンクからアカウントを作成する
   - メールアドレスのほか、Google / GitHub / LinkedIn / Microsoft アカウントでも登録できる
2. ログイン後のダッシュボードにある **API Keys** セクションから API キーをコピーする
   - キーは `tvly-` で始まる文字列
   - 追加のキーが必要な場合は、同セクションの **+** ボタンで作成できる（キー名と
     Key Type: Development（100 req/分）/ Production（1,000 req/分）を指定）
3. コピーしたキーを `TAVILY_API_KEY` として控えておく（`.env` への設定手順は後述）

> 無料プランでは月 1,000 API Credits まで利用できる（クレジットカード登録不要）。
> 詳細は [Tavily Quickstart](https://docs.tavily.com/documentation/quickstart) を参照。

### LangSmithのアカウント作成（任意）

> LangGraphサーバーのWeb UIを使用する場合に使用する

1. <https://smith.langchain.com/>にアクセスしてSign Up
2. ブラウザでログインしておく

## Notebook

- [`session08_tools.ipynb`](session08_tools.ipynb)

## パッケージ: `practical-agent`

`src/practical_agent` は、Notebookで扱った実務向け Tool と、短期・長期記憶・RAG を搭載した
AI エージェントのパッケージ版。

- **実務 Tool（`DEFAULT_TOOLS`）**: ファイル操作（`agent_workspace` 配下）、Web 検索/取得
  （Tavily）、HTTP、シェル（`run_command`）、Python 実行（`python_repl`）
- **知識ベース（`KnowledgeBase`）**: ドキュメント取り込みとセマンティック検索。
  `make_search_tool` で `search_knowledge_base` を追加
- **短期記憶**: `session_id`（スレッド）ごとに会話履歴を checkpointer で永続化
- **長期記憶**: `user_id` ごとに恒常的な事実を Store へ抽出・検証して保存

### ライブラリとして使用

```python
from practical_agent import Agent

agent = Agent()  # 既定で ChatOpenAI・埋め込み付き Store・DEFAULT_TOOLS を使用

# Web検索（web_search / fetch_url）とファイル操作（write_file）を組み合わせた例
# ファイルは agent_workspace/ 配下に保存される
print(
    agent.run(
        "LangChainのToolの概要を公式ドキュメントから調べ、"
        "要点を tool_research.md に保存してください",
        user_id="user-001",
        session_id="s1",
    )
)
```

### LangGraph Server として起動

1. プロジェクトルートに`.env`ファイルを作成し、APIキーを設定
   ```bash
   echo "OPENAI_API_KEY=sk-..." > .env
   echo "TAVILY_API_KEY=tvly-..." >> .env
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

グラフとストア設定は [`langgraph.json`](langgraph.json) で宣言する。

| グラフ | 役割 |
|---|---|
| `practical_agent` | 実務 Tool・RAG・記憶付きエージェント |
| `ingest` | ドキュメントの取り込み（LLM を使わない決定的なパイプライン） |

長期記憶のセマンティック検索設定（埋め込みモデル・次元・対象フィールド）は同ファイルの
`store.index` で定義するため、サーバー用エントリポイント（`server.py:make_graph`）は
**checkpointer / store を渡さずに** コンパイル（サーバーが自動注入）。

API 経由での取り込みと質問の例:

```bash
# 取り込み
curl -X POST localhost:2024/runs/wait -H 'Content-Type: application/json' \
  -d '{"assistant_id":"ingest","input":{"text":"リモートワークは週3日まで利用できる。","source":"社内規程集"}}'

# 質問（context.user_id が必須）
curl -X POST localhost:2024/runs/wait -H 'Content-Type: application/json' \
  -d '{"assistant_id":"practical_agent","input":{"messages":[{"role":"user","content":"規程を確認して要点を summary.md に保存して"}]},"context":{"user_id":"u1"}}'
```
