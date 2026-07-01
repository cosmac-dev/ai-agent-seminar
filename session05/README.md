# 第5回: Memory Management


## 事前準備

```bash
cd ai-agent-seminar/session05
python -m pip install -e .
```

## Notebook

[`session05_memory.ipynb`](session05_memory.ipynb)

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

> 実行には `OPENAI_API_KEY` が必要です。
```bash
python -m pip install -e ".[server]"   # langgraph-cli を含める
echo "OPENAI_API_KEY=sk-..." > .env      # langgraph.json が参照する
langgraph dev                            # http://127.0.0.1:2024 （Studio 付き）
```

グラフとストア設定は [`langgraph.json`](langgraph.json) で宣言しています。長期記憶の
セマンティック検索設定（埋め込みモデル・次元・対象フィールド）は同ファイルの `store.index`
で定義するため、サーバー用エントリポイント（`server.py:make_graph`）は
**checkpointer / store を渡さずに** コンパイルします（サーバーが自動注入）。

呼び出し例（`langgraph-sdk`）:

```python
from langgraph_sdk import get_client

client = get_client(url="http://127.0.0.1:2024")
thread = await client.threads.create()  # 短期記憶（スレッド）はサーバーが管理
await client.runs.wait(
    thread["thread_id"],
    "mnemonic_agent",
    input={"content": "覚えて: 私はPythonが好きです"},  # 入力はユーザーメッセージ本文のみ
    context={"user_id": "user-001"},  # 長期記憶の名前空間（Context.user_id）
)
```

