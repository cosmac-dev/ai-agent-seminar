# 第16回: フレームワーク

## 前提条件

1. Git
2. 実行環境（いずれか）
   - ローカルの Python 3.11 以上 ＋ Jupyter（または **VS Code** Jupyter 拡張機能）
   - **Dev Containers**（Docker 利用）
   - **Google Colab**
3. OpenAI の API キー（`OPENAI_API_KEY`）

本回では、同じ社内手続きの案内エージェントを、フレームワークを使わない OpenAI SDK と10個のフレームワークで実装し、
実装方式の違いを1枚の比較表とコードで確かめる。Notebook の実行は OpenAI のモデル（`gpt-5.4-mini`）を呼び出すため、利用料金が発生する。

## 事前準備

### リポジトリのクローン

```bash
git clone https://github.com/cosmac-dev/ai-agent-seminar.git
cd ai-agent-seminar/session16
```

既にクローン済みの場合は、ローカルの変更を保全して最新の教材に更新し、本回のディレクトリへ移動する。

### Notebook の実行

- ローカル: Python 3.11 以上の仮想環境で `python -m pip install -r requirements.txt` を実行し、その環境の Jupyter カーネルを選んで上から順にセルを実行する。
- Dev Container: VS Codeでリポジトリを開き、**Dev Containers: Reopen in Container** から `ai-agent-seminar-session16` を選ぶ。[専用設定](../.devcontainer/session16/devcontainer.json)が起動時に `session16/.venv` を作って `requirements.txt` を導入し、Notebook のカーネルにこの環境を使う。
- Colab: Notebook 冒頭の **Open in Colab** から開く。Notebook は単独で動作する。導入後に import のエラーが出た場合は、ランタイムを再起動して先頭から実行し直す。

API キーは Notebook の入力欄、または環境変数 `OPENAI_API_KEY` で設定する。キーをコード・出力・Git に保存しない。

Notebook 内ではトップレベルの `await` を使用する。`asyncio.run` は通常の Python スクリプトで使用する。

## Notebook

- [`session16_frameworks.ipynb`](session16_frameworks.ipynb)

## バージョンの固定

10個のフレームワークを1つの環境に入れるため、`requirements.txt` でバージョンを固定している。
新しい版を組み合わせると、`openai-agents` は `openai` の版で、`litellm` は `mcp` の版で CrewAI と衝突する。
動作確認に使用した Python は 3.12.15 と 3.13.17。
