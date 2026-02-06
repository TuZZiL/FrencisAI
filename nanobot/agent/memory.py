"""Memory system for persistent agent memory."""

from pathlib import Path
from datetime import datetime

from loguru import logger

from nanobot.utils.helpers import ensure_dir, today_date


class MemoryStore:
    """
    Memory system for the agent.

    Supports daily notes (memory/YYYY-MM-DD.md) and long-term memory (MEMORY.md).
    Optionally backed by ChromaDB for semantic search (RAG).
    """

    def __init__(self, workspace: Path, chroma_dir: Path | None = None):
        self.workspace = workspace
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self._vector = None

        # Initialize vector store if chromadb available
        if chroma_dir is not None:
            from nanobot.agent.vectorstore import is_available
            if is_available():
                try:
                    from nanobot.agent.vectorstore import VectorStore
                    self._vector = VectorStore(chroma_dir)
                    if self._vector.count() == 0:
                        self._reindex_all()
                except Exception as e:
                    logger.warning(f"Failed to initialize VectorStore: {e}")
                    self._vector = None
            else:
                logger.info("chromadb not installed — RAG disabled (pip install chromadb)")

    def get_today_file(self) -> Path:
        """Get path to today's memory file."""
        return self.memory_dir / f"{today_date()}.md"

    def read_today(self) -> str:
        """Read today's memory notes."""
        today_file = self.get_today_file()
        if today_file.exists():
            return today_file.read_text(encoding="utf-8")
        return ""

    def append_today(self, content: str) -> None:
        """Append content to today's memory notes."""
        today_file = self.get_today_file()

        if today_file.exists():
            existing = today_file.read_text(encoding="utf-8")
            content = existing + "\n" + content
        else:
            # Add header for new day
            header = f"# {today_date()}\n\n"
            content = header + content

        today_file.write_text(content, encoding="utf-8")

        if self._vector:
            try:
                self._vector.upsert_file(today_file, doc_type="daily")
            except Exception as e:
                logger.warning(f"Failed to upsert today's notes to vector store: {e}")

    def read_long_term(self) -> str:
        """Read long-term memory (MEMORY.md)."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        """Write to long-term memory (MEMORY.md)."""
        self.memory_file.write_text(content, encoding="utf-8")

        if self._vector:
            try:
                self._vector.upsert_file(self.memory_file, doc_type="long_term")
            except Exception as e:
                logger.warning(f"Failed to upsert MEMORY.md to vector store: {e}")

    def get_recent_memories(self, days: int = 7) -> str:
        """
        Get memories from the last N days.

        Args:
            days: Number of days to look back.

        Returns:
            Combined memory content.
        """
        from datetime import timedelta

        memories = []
        today = datetime.now().date()

        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.memory_dir / f"{date_str}.md"

            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                memories.append(content)

        return "\n\n---\n\n".join(memories)

    def list_memory_files(self) -> list[Path]:
        """List all memory files sorted by date (newest first)."""
        if not self.memory_dir.exists():
            return []

        files = list(self.memory_dir.glob("????-??-??.md"))
        return sorted(files, reverse=True)

    def get_memory_context(self, query: str | None = None) -> str:
        """
        Get memory context for the agent.

        Args:
            query: Optional user query for semantic search.

        Returns:
            Formatted memory context including long-term and recent memories.
        """
        parts = []

        # Long-term memory — always included in full
        long_term = self.read_long_term()
        if long_term:
            parts.append("## Long-term Memory\n" + long_term)

        # Today's notes — always included in full
        today = self.read_today()
        if today:
            parts.append("## Today's Notes\n" + today)

        # RAG: semantic search over past daily notes
        if query and self._vector:
            # Refresh today's file in the index before searching
            today_file = self.get_today_file()
            if today_file.exists():
                try:
                    self._vector.upsert_file(today_file, doc_type="daily")
                except Exception:
                    pass

            # Exclude today's chunks (already shown above) via metadata filter
            today_stem = today_date()
            where = {"$and": [{"type": "daily"}, {"source": {"$ne": today_stem}}]}
            results = self._vector.search(query, n_results=5, where=where)
            if results:
                chunks = "\n\n---\n\n".join(results)
                parts.append("## Relevant Past Memories\n" + chunks)

        return "\n\n".join(parts) if parts else ""

    def search_memory(self, query: str, n_results: int = 10) -> str:
        """Search memory semantically. Used by memory_search tool."""
        if not self._vector:
            return "Semantic search unavailable (chromadb not installed). Use read_file to read memory files directly."

        # Ensure today is indexed
        today_file = self.get_today_file()
        if today_file.exists():
            try:
                self._vector.upsert_file(today_file, doc_type="daily")
            except Exception:
                pass

        results = self._vector.search(query, n_results=n_results)
        if not results:
            return f"No memories found for: {query}"

        lines = [f"Found {len(results)} relevant memory fragments:\n"]
        for i, chunk in enumerate(results, 1):
            lines.append(f"--- Fragment {i} ---\n{chunk}\n")
        return "\n".join(lines)

    def _reindex_all(self) -> None:
        """Index all existing memory files into the vector store."""
        if not self._vector:
            return

        total = 0

        # Index MEMORY.md
        if self.memory_file.exists():
            total += self._vector.upsert_file(self.memory_file, doc_type="long_term")

        # Index all daily files
        for f in self.list_memory_files():
            total += self._vector.upsert_file(f, doc_type="daily")

        logger.info(f"Reindexed memory: {total} chunks from {len(self.list_memory_files())} daily files + MEMORY.md")
