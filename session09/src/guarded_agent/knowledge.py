"""RAG検索の対象となる知識ベース。

取り込み（チャンク化 → 埋め込み → ベクトルストア保存）と
セマンティック検索を提供する。取り込みは判断の要らない決定的な前処理のため、
LLM やエージェントを介さず、この API を直接呼び出す。
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_CHUNK_SIZE = 200
DEFAULT_CHUNK_OVERLAP = 40
DEFAULT_TOP_K = 3


def _default_embeddings() -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=DEFAULT_EMBEDDING_MODEL)


class KnowledgeBase:
    """ドキュメントの取り込みとセマンティック検索を担う知識ベース。"""

    def __init__(
        self,
        embeddings: Embeddings | None = None,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self._vectorstore = InMemoryVectorStore(embeddings or _default_embeddings())

    def add_text(self, text: str, *, source: str = "unknown") -> int:
        """テキスト1件を取り込み、作成されたチャンク数を返す。"""
        document = Document(page_content=text, metadata={"source": source})
        return self.add_documents([document])

    def add_documents(self, documents: list[Document]) -> int:
        """Document のリストを取り込み、作成されたチャンク数を返す。"""
        chunks = self._splitter.split_documents(documents)
        if chunks:
            self._vectorstore.add_documents(chunks)
        return len(chunks)

    def add_file(self, path: str | Path, *, source: str | None = None) -> int:
        """テキストファイルを取り込み、作成されたチャンク数を返す。"""
        path = Path(path)
        return self.add_text(
            path.read_text(encoding="utf-8"),
            source=source or path.name,
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[tuple[Document, float]]:
        """関連チャンクを類似度スコア付きで返す。"""
        return self._vectorstore.similarity_search_with_score(query, k=top_k)

    def search_text(self, query: str, *, top_k: int = DEFAULT_TOP_K) -> str:
        """ツールの観測として使いやすい整形済みテキストで検索結果を返す。"""
        results = self.search(query, top_k=top_k)
        if not results:
            return "関連するドキュメントは見つかりませんでした。"

        formatted: list[str] = []
        for idx, (doc, score) in enumerate(results, start=1):
            source = doc.metadata.get("source", "unknown")
            formatted.append(
                f"[{idx}] source={source} similarity={score:.3f}\n{doc.page_content}"
            )
        return "\n\n".join(formatted)
