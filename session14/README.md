# 第14回 A2A（Agent2Agent）

## Notebook

- [`session14_a2a.ipynb`](session14_a2a.ipynb)

A2A の概念、MCP との役割分担、Agent の探索からタスク委譲・結果受信までを扱います。
この README は実行環境の準備とサーバーの起動手順をまとめたものです。

LLM 呼び出しと Agent Card の埋め込み生成には `OPENAI_API_KEY` が必要です。
MCP Server の起動時から埋め込み API を利用します。依存パッケージの導入と回帰テストは
OpenAI API を呼び出しません。

## ディレクトリ構成

`session14/` 内の主要なファイル・ディレクトリと役割は次のとおりです。

| ファイル・ディレクトリ | 役割 |
| --- | --- |
| [`session14_a2a.ipynb`](session14_a2a.ipynb) | 概念の解説とハンズオン。起動済みのサーバー群へ接続し、Agent の探索・タスク委譲・結果受信を確認 |
| [`run.sh`](run.sh) | MCP Server と5体の A2A Server の起動・終了時の停止をまとめるスクリプト。`--serve` で起動を維持し、省略時は MCP の探索確認後に終了 |
| [`pyproject.toml`](pyproject.toml)、[`uv.lock`](uv.lock) | Python の要件、依存パッケージ、CLI の定義と依存バージョンの固定 |
| `.env`（各自作成） | API キーやモデル名を設定するファイル。Git には保存しない |
| [`langgraph.json`](langgraph.json) | LangGraph Server のグラフと環境設定。Studio の入口 `a2a_demo` を宣言 |
| [`agent_cards/`](agent_cards/) | 各 Agent の名前・接続先・スキルなどを記述する Agent Card。MCP Server が配布・検索に使用 |
| [`src/a2a_mcp/agents/`](src/a2a_mcp/agents/) | A2A Server の起動処理と、Orchestrator・Planner・旅行手配 Agent の実装 |
| [`src/a2a_mcp/mcp/`](src/a2a_mcp/mcp/) | Agent Card のレジストリと旅行データ検索 Tool を提供する MCP Server、および探索確認用クライアント |
| [`src/a2a_mcp/common/`](src/a2a_mcp/common/) | A2A 通信、Task の実行・状態更新、担当 Agent の探索とワークフロー制御、共通の型・プロンプト |
| [`src/a2a_mcp/studio_graph.py`](src/a2a_mcp/studio_graph.py) | Studio の入力を Orchestrator へ転送し、応答と Task の状態を返すグラフ |
| [`travel_agency.db`](travel_agency.db) | 航空券・ホテル・レンタカー候補を検索するための固定データを収めた SQLite DB |
| [`tests/`](tests/) | 外部 API を使わずに実行する回帰テスト |
| [`assets/`](assets/) | Notebook で使う A2A の概要図 |

## 実行環境

- VS Code（ローカル）: Python 3.13 以上、uv、Bash、Python・Jupyter 拡張機能
- VS Code（Dev Container）: Docker と Dev Containers 拡張機能

Windows では Dev Container を推奨します。ローカルでは、WSL など Python と Bash を
同じ環境で実行できる構成を使用してください。
ハンズオンでは MCP Server 1つと A2A Server 5体を起動し、Notebook から同じ環境の
`localhost` へ接続します。Colab の前提と依存導入は[下記](#google-colab)を参照してください。

## 事前準備

### リポジトリのクローン

```bash
git clone https://github.com/cosmac-dev/ai-agent-seminar.git
cd ai-agent-seminar/session14
```

既にクローン済みの場合は、ローカルの変更を保全して最新の教材に更新し、`session14/` に移動します。
以降のコマンドは、特記がない限りこのディレクトリで実行してください。

### 依存パッケージのインストール

```bash
uv sync --locked
```

[`uv.lock`](uv.lock) に従って `.venv/` を作成し、Notebook 用の `ipykernel` も導入します。
Notebook のカーネルには、この `.venv/` の Python を選択してください。
本教材は **a2a-sdk 0.3.26 / A2A 0.3系** を使用します。

### Google Colab

Python 3.13 以上の実行カーネルと Bash が必要です。条件を満たさないランタイムでは
初期化を停止するため、対応するランタイムを選ぶか Dev Container を使用してください。

リポジトリを用意して `session14/` に移動し、Notebook の `IS_COLAB` を `True` にして
導入セルを実行します。`uv sync --locked` でサーバー用 `.venv/` を作成し、同じ `uv.lock`
の実行時依存と教材パッケージを Colab の実行カーネルにも導入します。
既に関連パッケージを import 済みの場合は、カーネルを再起動して先頭から実行してください。

API キーの設定とサーバー起動は自動化していません。下記の手順で `.env` を設定し、
同じランタイム内の別端末などで `bash run.sh --serve` を起動したまま Notebook を実行します。
Colab での実サービス接続は未検証です。

### API キーの設定

`session14/.env` をエディターで作成し、使用する API キーを設定します。
既にファイルがある場合は、既存の設定を残して必要な項目を編集してください。

```dotenv
OPENAI_API_KEY=取得したAPIキー
```

キーを Notebook や Git に保存しないでください。
モデルを変更する場合は、同じファイルに次の項目を追加します。

| 環境変数 | 既定値・用途 |
| --- | --- |
| `OPENAI_MODEL` | `gpt-4o-mini`。各 Agent の LLM |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small`。Agent Card の検索 |
| `GOOGLE_PLACES_API_KEY` | 任意。`query_places_data` を使う場合のみ必要。基本演習では設定不要 |

### VS Code（Dev Container）利用時の注意

共通の導入手順は[ルート README](../README.md)を参照してください。
構成は `ai-agent-seminar-session14` を選択します。
[`post-create.sh`](../.devcontainer/session14/post-create.sh) が `uv sync --locked` を実行します。

ホストの `CMC_OPENAI_API_KEY` はコンテナ内の `OPENAI_API_KEY` へ引き継がれます。
この方法でキーを渡す場合、`.env` に同じキーを書く必要はありませんが、
LangGraph の設定が参照するため `.env` 自体は作成してください。内容は空でも構いません。
キーを変更した場合は VS Code とコンテナを開き直します。

## パッケージ: `a2a-mcp`

`src/a2a_mcp` は、MCP を Agent Card のレジストリとして使い、
A2A で旅行手配を分担するサンプル実装です。

| サーバー | ポート | 役割 |
| --- | ---: | --- |
| MCP Server | 10100 | Agent Card の配布・検索、旅行データの検索 Tool |
| Orchestrator Agent | 10101 | 計画の依頼、担当 Agent の探索・呼び出し、結果の要約 |
| Planner Agent | 10102 | 依頼の分解と不足情報の確認（LangGraph） |
| Air Ticketing Agent | 10103 | 航空券候補の検索と模擬手配（Google ADK） |
| Hotel Booking Agent | 10104 | ホテル候補の検索と模擬手配（Google ADK） |
| Car Rental Agent | 10105 | レンタカー候補の検索と模擬手配（Google ADK） |

### サーバーとして起動

```bash
bash run.sh --serve
```

6つのサーバーが起動したら、Notebook を開き、ハンズオンのセルを上から実行します。
サーバーの端末は起動したままにしてください。ログの保存先は起動時に表示されます。
`--serve` を付けない場合は、MCP の探索確認を実行して終了します。この確認も API を利用します。

### LangGraph Server として起動

Notebook の代わりに Studio を使う場合は、サーバー群を起動したまま、
別の端末の `session14/` で次を実行します。

```bash
uv run --locked langgraph dev --no-browser
```

端末に表示された Studio URL を開き、`a2a_demo` を選択します。
Studio 側でログインを求められた場合は、その案内に従ってください。
グラフは [`langgraph.json`](langgraph.json) で宣言しています。

| グラフ | 役割 |
| --- | --- |
| `a2a_demo` | Studio の入力を Orchestrator へ転送する入口。LangGraph Server は既定でポート2024を使用 |

`input-required` が返った場合は、同じ Studio スレッドで回答します。
Notebook と Studio は同時に使用せず、どちらか一方で会話を進めてください。

### サーバーの停止

`run.sh --serve` と LangGraph Server を実行している各端末で `Ctrl+C` を押します。
A2A Task はメモリ上に保持するため、再起動後は新しい Notebook の会話、
または新しい Studio スレッドから開始してください。

## サンプルの制約

- **模擬手配**: `travel_agency.db` の固定データを検索して応答を生成します。実予約・決済は行いません。DB に日付別の空席・在庫情報はなく、例の2025年6月の日程で予約可能かは検証しません。予算検証と自動再計画も未実装です。
- **単一会話**: 1つのサーバー群で扱う会話は1つです。複数の context を並行処理するための状態分離は未対応です。
- **Agent の追加**: Agent Card は MCP 起動時に読み込みます。追加時は対応する Agent を起動し、MCP Server を再起動してください。
- **信頼境界**: ローカルの教材用サンプルです。外部 Agent の Card・Message・Artifact を信頼できるものとして扱わないでください。外部入力の安全性検証、接続先の認証・認可は本演習の対象外です。インターネットへ公開せず、管理下のサンプルだけを接続してください。

## トラブルシューティング

| 症状 | 確認する点 |
| --- | --- |
| `OPENAI_API_KEY is not set`、埋め込み生成に失敗 | `.env` またはコンテナに渡したキーと API の利用枠を確認。キーの値はログに出さない |
| ポート使用中で起動できない | 10100〜10105を使う前回のサーバーを終了する。Studio は2024も使用 |
| `ModuleNotFoundError`、カーネルが見つからない | `session14/` で `uv sync --locked` を実行し、その `.venv/` を選択 |
| Agent Card や DB が見つからない | カレントディレクトリが `session14/` か確認 |
| 再起動後に Task を再開できない | 古い Task ID を使わず、新しい会話を開始 |
| `failed` で終了する | 起動時に表示されたサーバーログで、下流 Agent の失敗・通信切断・タイムアウトを確認 |

## 動作確認

外部 API を使わず、SQL のエラー応答、Task の状態遷移、Notebook の JSON 例などを検証します。

```bash
uv run --locked python -m unittest discover -s tests -v
```

## 参考資料

- [A2A 0.3 仕様](https://a2a-protocol.org/v0.3.0/specification/)
- [元サンプル: a2a-samples / a2a_mcp](https://github.com/a2aproject/a2a-samples/tree/6603ba3/samples/python/agents/a2a_mcp)（Apache License 2.0）。本教材では LLM API を OpenAI に統一し、Notebook・Studio から実行できるように調整しています。
