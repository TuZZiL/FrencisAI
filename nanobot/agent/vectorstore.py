"""Vector store for semantic memory search using ChromaDB."""

from pathlib import Path

from loguru import logger


def is_available() -> bool:
    """Check if chromadb is installed."""
    try:
        import chromadb  # noqa: F401
        return True
    except ImportError:
        return False


class VectorStore:
    """Thin wrapper around ChromaDB for memory search."""

    MIN_CHUNK_LENGTH = 50

    def __init__(self, persist_dir: Path):
        import chromadb

        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name="memory",
            metadata={"hnsw:space": "cosine"},
        )
        logger.debug(f"VectorStore ready, {self._collection.count()} chunks in collection")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_file(self, file_path: Path, doc_type: str = "daily") -> int:
        """Read a .md file, split into paragraphs, and upsert chunks.

        Returns the number of chunks upserted.
        """
        if not file_path.exists():
            return 0

        text = file_path.read_text(encoding="utf-8")
        chunks = self._split_paragraphs(text)
        if not chunks:
            return 0

        source = file_path.stem  # e.g. "2025-06-01" or "MEMORY"
        ids = [f"{source}::{i}" for i in range(len(chunks))]
        metadatas = [{"source": source, "type": doc_type} for _ in chunks]

        self._collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        return len(chunks)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[str]:
        """Semantic search, returns chunk texts."""
        kwargs: dict = {"query_texts": [query], "n_results": n_results}
        if where:
            kwargs["where"] = where

        try:
            results = self._collection.query(**kwargs)
        except Exception as e:
            logger.warning(f"VectorStore search failed: {e}")
            return []

        docs = results.get("documents")
        if docs and docs[0]:
            return docs[0]
        return []

    def delete_by_source(self, source_name: str) -> None:
        """Delete all chunks from a given source."""
        self._collection.delete(where={"source": source_name})

    def count(self) -> int:
        """Total number of chunks in the collection."""
        return self._collection.count()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split text by double newline, filter short chunks."""
        paragraphs = text.split("\n\n")
        return [p.strip() for p in paragraphs if len(p.strip()) >= VectorStore.MIN_CHUNK_LENGTH]
