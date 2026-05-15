from __future__ import annotations

from pathlib import Path

from kairos.cli import main
from kairos.config import KairosPaths
from kairos.memory import MemoryStore


def test_reflect_cli_writes_journal_and_candidates(tmp_path: Path) -> None:
    result = main(
        [
            "reflect",
            "我喜欢先讨论架构再写代码，今天完成了 Kairos 日记闭环，也很有能量",
            "--date",
            "2026-05-15",
            "--root",
            str(tmp_path),
        ]
    )

    paths = KairosPaths.from_root(tmp_path)
    journal = paths.journal / "2026" / "05" / "2026-05-15.md"
    candidates = MemoryStore(paths).list(include_candidates=True)

    assert result == 0
    assert journal.exists()
    assert "Kairos 日记闭环" in journal.read_text(encoding="utf-8")
    assert candidates
    assert MemoryStore(paths).list() == []


def test_schedule_add_and_daemon_tick_cli_deliver_message(tmp_path: Path, capsys) -> None:
    add_result = main(
        [
            "schedule-add",
            "journal",
            "Journal Check",
            "--kind",
            "every",
            "--seconds",
            "60",
            "--message",
            "要写日记吗？",
            "--due-now",
            "--root",
            str(tmp_path),
        ]
    )
    tick_result = main(["daemon-tick", "--root", str(tmp_path)])
    output = capsys.readouterr().out

    assert add_result == 0
    assert tick_result == 0
    assert "要写日记吗？" in output
    assert "due_jobs: 1" in output
    assert "delivery_delivered: 1" in output
