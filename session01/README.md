# 第1回：LLMを動かして理解する①

## 事前準備

1. Google アカウント（Colab 使用のため）
2. Hugging Face Accessトークン（Read）の取得（下記「Hugging Face Accessトークンの取得」参照）
3. `session01_llm_basics.ipynb` を Colab で開けることを確認（下記「Colab でノートブックを開く」参照）

### Hugging Face Accessトークンの取得

ノートブックではモデルのダウンロードや `huggingface_hub` へのログインに **Read 権限** のAccessトークンを使います。無料アカウントで取得できます。

#### Hugging Face アカウントを作成する

1. [Hugging Face](https://huggingface.co/) を開く
2. 右上の **Sign Up** からアカウントを作成する（既にアカウントがある場合は **Log in**）
3. メール認証が求められたら、案内に従って完了する

#### Read Accessトークンを発行する

1. ログイン後、右上のプロフィールアイコン → **Settings** を開く  
   （直接開く場合: [Access Tokens](https://huggingface.co/settings/tokens)）
2. 左メニューの **Access Tokens** を選択
3. **Create new token** をクリック
4. 次のように設定する
   - **Token name**: 任意（例: `seminar-session01`）
   - **Token type**: **Read**（読み取り専用で十分です）
5. **Create token** を押し、表示されたAccessトークン（`hf_` で始まる文字列）をコピーする

> **重要**: Accessトークンは作成直後しか全文を表示されません。メモ帳などに控えてから画面を閉じてください。Colab への登録方法はセッション中に案内します。

Accessトークンは第三者に共有しないでください。GitHub などにコミットしないよう注意してください。

### Colab でノートブックを開く

同じ階層の [`session01_llm_basics.ipynb`](session01_llm_basics.ipynb) を Colab 上で開けるか、事前に確認してください。

1. GitHub 上で `session01/session01_llm_basics.ipynb` を開く
2. ノートブック先頭の **[Open In Colab]** をクリックする。Google に未ログインの場合はログイン画面が出るので、事前準備 1 のアカウントでログインする。Colab を初めて使う場合は、利用規約の同意やウェルカム画面が出ることがあるので、表示に従って進める
3. Colab で`session01_llm_basics.ipynb`が表示されることを確認する
