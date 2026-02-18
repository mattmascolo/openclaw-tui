from __future__ import annotations

import json
from pathlib import Path

import pytest

from openclaw_tui.transcript import (
    TranscriptMessage,
    read_transcript,
    read_task,
    read_report,
    read_transcript_incremental,
    get_last_activity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_jsonl(tmp_path: Path, agent_id: str, session_id: str, lines: list[dict]) -> Path:
    """Write a JSONL transcript file and return its path."""
    session_dir = tmp_path / "agents" / agent_id / "sessions"
    session_dir.mkdir(parents=True)
    file_path = session_dir / f"{session_id}.jsonl"
    file_path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
    return file_path


def msg_line(role: str, content, timestamp: str = "2024-01-15T14:30:00.000Z") -> dict:
    return {
        "type": "message",
        "timestamp": timestamp,
        "message": {"role": role, "content": content},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReadTranscriptMissingFile:
    def test_returns_empty_list_when_file_not_found(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        result = read_transcript("nonexistent-session", "main")
        assert result == []


class TestReadTranscriptFiltering:
    def test_only_message_lines_returned(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)

        lines = [
            {"type": "session", "data": "some session info"},
            msg_line("user", "hello"),
            {"type": "custom", "whatever": 42},
            msg_line("assistant", "world"),
        ]
        make_jsonl(tmp_path, "main", "sess1", lines)

        result = read_transcript("sess1", "main")
        assert len(result) == 2
        assert result[0].role == "user"
        assert result[1].role == "assistant"


class TestReadTranscriptRoleMapping:
    def test_user_role(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        make_jsonl(tmp_path, "main", "sess", [msg_line("user", "hi")])
        result = read_transcript("sess", "main")
        assert result[0].role == "user"

    def test_assistant_role(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        make_jsonl(tmp_path, "main", "sess", [msg_line("assistant", "hi back")])
        result = read_transcript("sess", "main")
        assert result[0].role == "assistant"

    def test_tool_result_role_mapped_to_tool(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        make_jsonl(tmp_path, "main", "sess", [msg_line("toolResult", "some result")])
        result = read_transcript("sess", "main")
        assert result[0].role == "tool"


class TestReadTranscriptStringContent:
    def test_string_content_used_directly(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        make_jsonl(tmp_path, "main", "sess", [msg_line("user", "Hello, world!")])
        result = read_transcript("sess", "main")
        assert result[0].content == "Hello, world!"


class TestReadTranscriptListContent:
    def test_extracts_text_from_text_block(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        content = [{"type": "text", "text": "Block text here"}]
        make_jsonl(tmp_path, "main", "sess", [msg_line("assistant", content)])
        result = read_transcript("sess", "main")
        assert result[0].content == "Block text here"

    def test_formats_tool_call_block(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        content = [{"type": "toolCall", "name": "exec"}]
        make_jsonl(tmp_path, "main", "sess", [msg_line("assistant", content)])
        result = read_transcript("sess", "main")
        assert result[0].content == "[tool: exec]"


class TestReadTranscriptLimit:
    def test_respects_limit_parameter(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)

        lines = [msg_line("user", f"message {i}") for i in range(30)]
        make_jsonl(tmp_path, "main", "sess", lines)

        result = read_transcript("sess", "main", limit=5)
        assert len(result) == 5

    def test_returns_last_n_messages(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)

        lines = [msg_line("user", f"message {i}") for i in range(10)]
        make_jsonl(tmp_path, "main", "sess", lines)

        result = read_transcript("sess", "main", limit=3)
        assert len(result) == 3
        assert result[0].content == "message 7"
        assert result[1].content == "message 8"
        assert result[2].content == "message 9"


class TestReadTranscriptTruncation:
    def test_truncates_content_to_max_content_len(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        long_text = "x" * 500
        make_jsonl(tmp_path, "main", "sess", [msg_line("user", long_text)])
        result = read_transcript("sess", "main", max_content_len=50)
        assert len(result[0].content) == 50
        assert result[0].content == "x" * 50


class TestReadTranscriptTimestamp:
    def test_extracts_hhmm_from_iso_timestamp(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        line = msg_line("user", "hi", timestamp="2024-03-22T09:45:30.123Z")
        make_jsonl(tmp_path, "main", "sess", [line])
        result = read_transcript("sess", "main")
        assert result[0].timestamp == "09:45"


class TestReadTranscriptMalformedLines:
    def test_skips_invalid_json_lines(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)

        session_dir = tmp_path / "agents" / "main" / "sessions"
        session_dir.mkdir(parents=True)
        file_path = session_dir / "sess.jsonl"
        # Mix of valid and invalid JSON
        file_path.write_text(
            '{"type": "message", "timestamp": "2024-01-01T10:00:00Z", "message": {"role": "user", "content": "good"}}\n'
            "NOT VALID JSON AT ALL\n"
            '{"type": "message", "timestamp": "2024-01-01T11:00:00Z", "message": {"role": "assistant", "content": "also good"}}\n',
            encoding="utf-8",
        )

        result = read_transcript("sess", "main")
        assert len(result) == 2
        assert result[0].content == "good"
        assert result[1].content == "also good"


# ---------------------------------------------------------------------------
# Helpers for new tests
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, lines: list[dict]) -> None:
    """Write JSONL lines to path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


def jsonl_path(tmp_path: Path, agent_id: str, session_id: str) -> Path:
    return tmp_path / "agents" / agent_id / "sessions" / f"{session_id}.jsonl"


def msg_rec(role: str, content, ts: str = "2026-02-18T01:44:10.123Z") -> dict:
    return {"type": "message", "timestamp": ts, "message": {"role": role, "content": content}}


# ---------------------------------------------------------------------------
# TestReadTask
# ---------------------------------------------------------------------------

class TestReadTask:
    def test_returns_first_user_message(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "s1")
        write_jsonl(path, [
            msg_rec("user", "Do this task", "2026-02-18T01:00:00.000Z"),
            msg_rec("assistant", "Sure", "2026-02-18T01:01:00.000Z"),
            msg_rec("user", "Another user msg", "2026-02-18T01:02:00.000Z"),
        ])
        result = read_task("s1", "agent1")
        assert result is not None
        assert result.role == "user"
        assert result.content == "Do this task"

    def test_returns_none_when_no_user_messages(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "s2")
        write_jsonl(path, [
            msg_rec("assistant", "Hello"),
            msg_rec("toolResult", "some result"),
        ])
        result = read_task("s2", "agent1")
        assert result is None

    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        result = read_task("no-such-session", "agent1")
        assert result is None

    def test_respects_max_content_len(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "s3")
        write_jsonl(path, [msg_rec("user", "A" * 500)])
        result = read_task("s3", "agent1", max_content_len=50)
        assert result is not None
        assert len(result.content) == 50


# ---------------------------------------------------------------------------
# TestReadReport
# ---------------------------------------------------------------------------

class TestReadReport:
    def test_returns_last_assistant_message(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "r1")
        write_jsonl(path, [
            msg_rec("user", "Do something"),
            msg_rec("assistant", "Working on it"),
            msg_rec("user", "Thanks"),
            msg_rec("assistant", "Done! Here is the final report."),
        ])
        result = read_report("r1", "agent1")
        assert result is not None
        assert result.role == "assistant"
        assert result.content == "Done! Here is the final report."

    def test_returns_none_when_no_assistant_messages(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "r2")
        write_jsonl(path, [
            msg_rec("user", "Hello"),
            msg_rec("toolResult", "some output"),
        ])
        result = read_report("r2", "agent1")
        assert result is None

    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        result = read_report("no-such-session", "agent1")
        assert result is None

    def test_picks_last_not_first_assistant(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "r3")
        write_jsonl(path, [
            msg_rec("assistant", "First assistant message"),
            msg_rec("assistant", "Second assistant message"),
            msg_rec("assistant", "Third assistant message - final"),
        ])
        result = read_report("r3", "agent1")
        assert result is not None
        assert result.content == "Third assistant message - final"


# ---------------------------------------------------------------------------
# TestReadTranscriptIncremental
# ---------------------------------------------------------------------------

class TestReadTranscriptIncremental:
    def test_reads_full_file_when_offset_zero(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "inc1")
        write_jsonl(path, [
            msg_rec("user", "Hello"),
            msg_rec("assistant", "Hi there"),
        ])
        msgs, new_offset = read_transcript_incremental("inc1", "agent1", offset=0)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        assert new_offset > 0

    def test_reads_only_new_content_after_offset(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "inc2")
        path.parent.mkdir(parents=True, exist_ok=True)
        line1 = json.dumps(msg_rec("user", "First message")) + "\n"
        path.write_bytes(line1.encode("utf-8"))
        # Read full file first
        msgs, offset = read_transcript_incremental("inc2", "agent1", offset=0)
        assert len(msgs) == 1
        assert msgs[0].content == "First message"

        # Append a second line
        line2 = json.dumps(msg_rec("assistant", "Second message")) + "\n"
        with open(path, "ab") as f:
            f.write(line2.encode("utf-8"))

        # Read only new content
        msgs2, offset2 = read_transcript_incremental("inc2", "agent1", offset=offset)
        assert len(msgs2) == 1
        assert msgs2[0].content == "Second message"
        assert offset2 > offset

    def test_returns_empty_when_file_unchanged(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "inc3")
        write_jsonl(path, [msg_rec("user", "Hello")])
        file_size = path.stat().st_size
        msgs, new_offset = read_transcript_incremental("inc3", "agent1", offset=file_size)
        assert msgs == []
        assert new_offset == file_size

    def test_returns_empty_when_file_missing(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        msgs, offset = read_transcript_incremental("no-such-session", "agent1", offset=0)
        assert msgs == []
        assert offset == 0

    def test_returns_correct_new_offset(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "inc4")
        write_jsonl(path, [msg_rec("user", "Hello")])
        file_size = path.stat().st_size
        msgs, new_offset = read_transcript_incremental("inc4", "agent1", offset=0)
        assert new_offset == file_size

    def test_handles_partial_line_at_offset_boundary(self, tmp_path, monkeypatch):
        """Seeking mid-line should not crash; the partial line is skipped gracefully."""
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "inc5")
        path.parent.mkdir(parents=True, exist_ok=True)
        line1 = json.dumps(msg_rec("user", "Complete first line")) + "\n"
        line2 = json.dumps(msg_rec("assistant", "Complete second line")) + "\n"
        path.write_bytes((line1 + line2).encode("utf-8"))

        # Seek to a byte in the middle of line1 (e.g. byte 5)
        msgs, new_offset = read_transcript_incremental("inc5", "agent1", offset=5)
        # Should not crash; partial line1 is invalid JSON, but line2 should be parsed
        assert new_offset == len(line1.encode("utf-8")) + len(line2.encode("utf-8"))
        # May or may not have the second message depending on split, but at minimum no crash
        # The second full line should be recovered
        contents = [m.content for m in msgs]
        assert "Complete second line" in contents


# ---------------------------------------------------------------------------
# TestGetLastActivity
# ---------------------------------------------------------------------------

class TestGetLastActivity:
    def test_returns_last_message_content(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "la1")
        write_jsonl(path, [
            msg_rec("user", "First message"),
            msg_rec("assistant", "Second message"),
            msg_rec("user", "Third message"),
        ])
        result = get_last_activity("la1", "agent1", max_len=200)
        assert result == "Third message"

    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        result = get_last_activity("no-such-session", "agent1")
        assert result is None

    def test_truncates_to_max_len(self, tmp_path, monkeypatch):
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "la2")
        write_jsonl(path, [msg_rec("user", "X" * 200)])
        result = get_last_activity("la2", "agent1", max_len=20)
        assert result is not None
        assert len(result) == 20

    def test_reads_from_large_file_efficiently(self, tmp_path, monkeypatch):
        """Writes >4KB of padding lines, then adds a final recognisable message."""
        import openclaw_tui.transcript as t
        monkeypatch.setattr(t, "OPENCLAW_DIR", tmp_path)
        path = jsonl_path(tmp_path, "agent1", "la3")
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write enough data to exceed the 4096 byte read window
        padding = []
        chunk = "P" * 100
        for _ in range(50):  # ~100 bytes each line => ~5KB
            padding.append(msg_rec("user", chunk))
        # Final message that must be found
        padding.append(msg_rec("assistant", "FinalActivity"))
        write_jsonl(path, padding)
        assert path.stat().st_size > 4096
        result = get_last_activity("la3", "agent1", max_len=200)
        assert result == "FinalActivity"
