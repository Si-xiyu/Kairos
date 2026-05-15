"""Memory storage layer."""

from datetime import date
from pathlib import Path

from kairos.memory.model import MemoryEntry, MemoryType, MemoryScope


class MemoryStore:
    """Store for memory entries with frontmatter + content format."""

    def __init__(self, base_dir: Path | None = None):
        """Initialize with base directory for memory storage.

        If not provided, uses .kairos/memory in current directory.
        """
        if base_dir is None:
            base_dir = Path(".kairos/memory")
        self.base_dir = Path(base_dir)
        self.candidates_dir = self.base_dir / "candidates"
        self.index_file = self.base_dir / "MEMORY.md"

    def _type_dir(self, mem_type: MemoryType) -> Path:
        """Get directory for a memory type."""
        return self.base_dir / mem_type.value

    def _ensure_dirs(self) -> None:
        """Ensure all type directories exist."""
        for mem_type in MemoryType:
            self._type_dir(mem_type).mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    def save(self, entry: MemoryEntry) -> Path:
        """Save a memory entry to disk.

        Returns the path where the entry was saved.
        """
        self._ensure_dirs()

        # Auto types go to candidates dir
        auto_types = (
            MemoryType.LIFE_PATTERN,
            MemoryType.ENERGY_PATTERN,
            MemoryType.REFLECTION_THEME,
        )
        if entry.type in auto_types:
            target_dir = self.candidates_dir
        else:
            target_dir = self._type_dir(entry.type)

        file_path = target_dir / f"{entry.name}.md"

        content = f"---\n{entry.to_frontmatter()}\n---\n\n{entry.content}"
        file_path.write_text(content, encoding="utf-8")

        return file_path

    def load(self, path_or_name: str | Path) -> MemoryEntry:
        """Load a memory entry by path or name."""
        if "/" in str(path_or_name) or "\\" in str(path_or_name) or Path(path_or_name).exists():
            # It's a path
            path = Path(path_or_name)
        else:
            # It's a name - search in all dirs
            path = self._find_memory_path(path_or_name)

        if not path or not path.exists():
            raise FileNotFoundError(f"Memory not found: {path_or_name}")

        text = path.read_text(encoding="utf-8")
        return MemoryEntry.from_frontmatter(text)

    def _find_memory_path(self, name: str) -> Path | None:
        """Find the path for a memory by name."""
        # Search in candidates first, then all type dirs
        candidates_path = self.candidates_dir / f"{name}.md"
        if candidates_path.exists():
            return candidates_path

        for mem_type in MemoryType:
            path = self._type_dir(mem_type) / f"{name}.md"
            if path.exists():
                return path
        return None

    def list(self, mem_type: MemoryType | None = None) -> list[MemoryEntry]:
        """List all memory entries, optionally filtered by type."""
        entries = []

        if mem_type:
            type_dirs = [self._type_dir(mem_type)]
            if mem_type in (
                MemoryType.LIFE_PATTERN,
                MemoryType.ENERGY_PATTERN,
                MemoryType.REFLECTION_THEME,
            ):
                type_dirs = [self.candidates_dir]
        else:
            type_dirs = [self._type_dir(t) for t in MemoryType] + [self.candidates_dir]

        for type_dir in type_dirs:
            if not type_dir.exists():
                continue
            for md_file in type_dir.glob("*.md"):
                try:
                    entry = self.load(md_file)
                    entries.append(entry)
                except Exception:
                    # Skip invalid files
                    continue

        return entries

    def delete(self, name: str) -> bool:
        """Delete a memory entry by name.

        Returns True if deleted, False if not found.
        """
        path = self._find_memory_path(name)
        if path and path.exists():
            path.unlink()
            return True
        return False

    def rebuild_index(self) -> Path:
        """Rebuild the MEMORY.md index file.

        Returns the path to the index file.
        """
        self._ensure_dirs()

        entries = self.list()
        lines = ["# Memory Index\n", "## All Memories\n"]

        # Group by type
        by_type: dict[str, list[MemoryEntry]] = {}
        for entry in entries:
            type_key = entry.type.value
            if type_key not in by_type:
                by_type[type_key] = []
            by_type[type_key].append(entry)

        for mem_type in sorted(by_type.keys()):
            lines.append(f"\n### {mem_type}\n")
            for entry in sorted(by_type[mem_type], key=lambda e: e.name):
                lines.append(f"- [[{entry.name}]]: {entry.description}")

        self.index_file.write_text("\n".join(lines), encoding="utf-8")
        return self.index_file