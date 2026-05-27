from __future__ import annotations

from pathlib import Path

from kairos.config import KairosPaths
from kairos.memory.model import MemoryEntry, MemoryType

AUTO_CANDIDATE_TYPES = {
    MemoryType.LIFE_PATTERN,
    MemoryType.ENERGY_PATTERN,
    MemoryType.REFLECTION_THEME,
}


class MemoryStore:
    def __init__(self, paths: KairosPaths | None = None, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = paths.memory if paths is not None else Path(".kairos/memory")
        self.base_dir = Path(base_dir)
        self.candidates_dir = self.base_dir / "candidates"
        self.index_path = self.base_dir / "MEMORY.md"

    def save(self, entry: MemoryEntry, candidate: bool | None = None) -> Path:
        self._ensure_dirs()
        if candidate is None:
            candidate = entry.type in AUTO_CANDIDATE_TYPES
        target_dir = self.candidates_dir if candidate else self.base_dir / entry.type.value
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{_safe_name(entry.name)}.md"
        path.write_text(entry.to_markdown(), encoding="utf-8")
        if not candidate:
            self.rebuild_index()
        return path

    def load(self, path_or_name: str | Path, include_candidates: bool = True) -> MemoryEntry:
        path = self._resolve(path_or_name, include_candidates=include_candidates)
        if path is None or not path.exists():
            raise FileNotFoundError(f"Memory not found: {path_or_name}")
        return MemoryEntry.from_markdown(path.read_text(encoding="utf-8"))

    def list(
        self,
        mem_type: MemoryType | None = None,
        include_candidates: bool = False,
    ) -> list[MemoryEntry]:
        return [entry for entry, _path, _candidate in self.list_with_paths(mem_type, include_candidates)]

    def list_with_paths(
        self,
        mem_type: MemoryType | None = None,
        include_candidates: bool = False,
    ) -> list[tuple[MemoryEntry, Path, bool]]:
        dirs: list[Path]
        if mem_type is None:
            dirs = [self.base_dir / item.value for item in MemoryType]
        elif mem_type in AUTO_CANDIDATE_TYPES and include_candidates:
            dirs = [self.candidates_dir, self.base_dir / mem_type.value]
        else:
            dirs = [self.base_dir / mem_type.value]

        if include_candidates and mem_type is None:
            dirs.append(self.candidates_dir)

        entries: list[tuple[MemoryEntry, Path, bool]] = []
        for directory in dirs:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.md")):
                entries.append(
                    (
                        MemoryEntry.from_markdown(path.read_text(encoding="utf-8")),
                        path,
                        directory == self.candidates_dir,
                    )
                )
        return entries

    def delete(self, name: str, include_candidates: bool = True) -> bool:
        path = self._resolve(name, include_candidates=include_candidates)
        if path is None or not path.exists():
            return False
        path.unlink()
        self.rebuild_index()
        return True

    def confirm_candidate(self, name: str) -> Path:
        path = self._resolve_candidate(name)
        if path is None or not path.exists():
            raise FileNotFoundError(f"Memory candidate not found: {name}")
        entry = MemoryEntry.from_markdown(path.read_text(encoding="utf-8"))
        confirmed_path = self.save(entry, candidate=False)
        path.unlink()
        self.rebuild_index()
        return confirmed_path

    def delete_candidate(self, name: str) -> bool:
        path = self._resolve_candidate(name)
        if path is None or not path.exists():
            return False
        path.unlink()
        return True

    def rebuild_index(self) -> Path:
        self._ensure_dirs()
        entries = self.list(include_candidates=False)
        lines = ["# Memory Index", ""]
        if not entries:
            lines.append("_No confirmed memories yet._")
        for mem_type in MemoryType:
            typed = [entry for entry in entries if entry.type == mem_type]
            if not typed:
                continue
            lines.extend(["", f"## {mem_type.value}", ""])
            for entry in sorted(typed, key=lambda item: item.name):
                lines.append(f"- {entry.name}: {entry.description} [{entry.type.value}]")
        self.index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return self.index_path

    def _ensure_dirs(self) -> None:
        for mem_type in MemoryType:
            (self.base_dir / mem_type.value).mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path_or_name: str | Path, include_candidates: bool) -> Path | None:
        value = Path(path_or_name)
        if value.exists() or value.suffix == ".md" or value.parent != Path("."):
            return value
        safe = _safe_name(str(path_or_name))
        for mem_type in MemoryType:
            path = self.base_dir / mem_type.value / f"{safe}.md"
            if path.exists():
                return path
        if include_candidates:
            candidate = self.candidates_dir / f"{safe}.md"
            if candidate.exists():
                return candidate
        return None

    def _resolve_candidate(self, name: str) -> Path | None:
        value = Path(name)
        if value.exists() or value.suffix == ".md" or value.parent != Path("."):
            return value
        return self.candidates_dir / f"{_safe_name(name)}.md"


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return cleaned.strip("_") or "memory"
