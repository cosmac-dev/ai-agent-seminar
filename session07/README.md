# 第7回: RAG

## Notebook

- [`session07_rag.ipynb`](session07_rag.ipynb)

## パッケージ: `rag_agent`

`src/rag_agent` は、RAGをツールとして追加したAIエージェント。

- **知識ベース（`KnowledgeBase`）**: ドキュメントの取り込み（チャンク化 → 埋め込み →
  `InMemoryVectorStore` へ保存）とセマンティック検索を提供。検索対象はハードコードせず、
  実行時に取り込む
- **RAG検索ツール（`make_search_tool`）**: 知識ベースに束縛された `search_knowledge_base`
  ツールを生成し、エージェントが質問に応じて関連チャンクを検索する
- **短期記憶**: `session_id`（スレッド）ごとに会話履歴を checkpointer で永続化
- **長期記憶**: `user_id` ごとに恒常的な事実を Store へ抽出・検証して保存

### 取り込み（ingest）の設計

チャンク化 → 埋め込み → 保存は判断の要らない決定的な前処理のため、**LLM やエージェントを
介さず、API として直接呼び出す**設計にしている（エージェントのツールにすると、ドキュメント
全文が LLM のコンテキストを通ってトークンコストとサイズ制限の問題が生じるうえ、ツールが
呼ばれるかどうかも非決定的になる）。

- ライブラリ用途: `Agent.ingest()` / `Agent.ingest_file()` / `KnowledgeBase.add_text()`
- LangGraph Server 用途: 実行中のサーバーには Python API を直接呼ぶ手段が無いため、
  取り込み専用の `ingest` グラフを公開し、API 経由で取り込む

### ライブラリとして使用

```python
from rag_agent import Agent

agent = Agent()

# ドキュメントを取り込む（チャンク化 → 埋め込み → ベクトルストア保存）
agent.ingest(open("company_policy.txt", encoding="utf-8").read(), source="社内規程集")
# ファイルパス指定でも取り込める
# agent.ingest_file("company_policy.txt")

print(
    agent.run(
        "リモートワークは週何日まで利用できますか？",
        user_id="user-001",
        session_id="s1",
    )
)
```

### LangGraph Server として起動

1. `.env` ファイルに `OPENAI_API_KEY` を設定

   ```bash
   echo "OPENAI_API_KEY=sk-..." > .env
   ```

2. パッケージをインストール

   ```bash
   pip install -e ".[server]"
   ```

3. 起動

   ```bash
   langgraph dev
   # Colabの場合は langgraph dev --tunnel
   ```

グラフは [`langgraph.json`](langgraph.json) で2つ宣言している。

| グラフ | 役割 |
|---|---|
| `ingest` | ドキュメントの取り込み（LLM を使わない決定的なパイプライン） |
| `rag_agent` | RAG検索ツール付きエージェント |

API 経由での取り込みと質問の例:

```bash
# 取り込み
curl -X POST localhost:2024/runs/wait -H 'Content-Type: application/json' \
  -d '{"assistant_id":"ingest","input":{"text":"リモートワークは週3日まで利用できる。","source":"社内規程集"}}'

# 質問（context.user_id が必須）
curl -X POST localhost:2024/runs/wait -H 'Content-Type: application/json' \
  -d '{"assistant_id":"rag_agent","input":{"messages":[{"role":"user","content":"リモートワークは週何日まで？"}]},"context":{"user_id":"u1"}}'
```

> 知識ベースはプロセス内のインメモリ実装のため、サーバーを再起動すると取り込んだ
> ドキュメントは消える。永続化したい場合は `KnowledgeBase` のベクトルストアを
> Chroma / pgvector などに差し替える。
