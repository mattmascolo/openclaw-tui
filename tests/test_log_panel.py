"""Tests for the LogPanel widget."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from textual.app import App, ComposeResult

from openclaw_tui.widgets.log_panel import LogPanel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class LogPanelTestApp(App[None]):
    """Minimal app for LogPanel tests."""

    def compose(self) -> ComposeResult:
        yield LogPanel()


class FakeMessage:
    """Stand-in for TranscriptMessage in tests."""

    def __init__(self, role: str, content: str, timestamp: str = "10:00") -> None:
        self.role = role
        self.content = content
        self.timestamp = timestamp


def _capture_writes(panel: LogPanel, fn) -> list[str]:
    """Call fn() while intercepting all LogPanel.write() calls.

    Returns a list of string representations of each write argument.
    """
    written: list[str] = []

    def _fake_write(content, **kwargs):
        written.append(str(content))

    with patch.object(panel, "write", side_effect=_fake_write):
        fn()

    return written


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_panel_shows_placeholder_initially() -> None:
    """LogPanel.show_placeholder() writes the placeholder text."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)
        written = _capture_writes(panel, panel.show_placeholder)

        assert any("Select a session to view logs" in w for w in written), (
            f"Expected placeholder text in writes: {written}"
        )


@pytest.mark.asyncio
async def test_log_panel_show_transcript_formats_messages() -> None:
    """show_transcript() writes formatted message lines."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        msgs = [
            FakeMessage("user", "Hello world", "09:00"),
            FakeMessage("assistant", "Hi there", "09:01"),
        ]

        written = _capture_writes(panel, lambda: panel.show_transcript(msgs))
        combined = " ".join(written)

        assert "Hello world" in combined, f"User message content missing: {written}"
        assert "Hi there" in combined, f"Assistant message content missing: {written}"
        assert "09:00" in combined, f"User timestamp missing: {written}"
        assert "09:01" in combined, f"Assistant timestamp missing: {written}"


@pytest.mark.asyncio
async def test_log_panel_show_transcript_empty_shows_no_messages() -> None:
    """show_transcript() with empty list shows 'No messages found'."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        written = _capture_writes(panel, lambda: panel.show_transcript([]))

        assert any("No messages found" in w for w in written), (
            f"Expected 'No messages found' in writes: {written}"
        )


@pytest.mark.asyncio
async def test_log_panel_show_error_displays_error_text() -> None:
    """show_error() writes an error message containing the provided text."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        written = _capture_writes(panel, lambda: panel.show_error("Something went wrong"))
        combined = " ".join(written)

        assert "Something went wrong" in combined, f"Error text missing: {written}"
        assert "Error" in combined, f"'Error' label missing: {written}"


@pytest.mark.asyncio
async def test_log_panel_user_messages_have_cyan_styling() -> None:
    """User messages are formatted with [bold cyan] Rich markup."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        msgs = [FakeMessage("user", "Hello", "10:00")]
        written = _capture_writes(panel, lambda: panel.show_transcript(msgs))
        combined = " ".join(written)

        assert "bold cyan" in combined, f"[bold cyan] markup missing: {written}"
        assert "Hello" in combined, f"Message content missing: {written}"


@pytest.mark.asyncio
async def test_log_panel_assistant_messages_have_green_styling() -> None:
    """Assistant messages are formatted with [bold green] Rich markup."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        msgs = [FakeMessage("assistant", "Hi there", "10:00")]
        written = _capture_writes(panel, lambda: panel.show_transcript(msgs))
        combined = " ".join(written)

        assert "bold green" in combined, f"[bold green] markup missing: {written}"
        assert "Hi there" in combined, f"Message content missing: {written}"


@pytest.mark.asyncio
async def test_log_panel_tool_messages_have_dim_styling() -> None:
    """Tool (non user/assistant) messages are formatted with [dim] Rich markup."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        msgs = [FakeMessage("tool", "[tool: bash]", "10:00")]
        written = _capture_writes(panel, lambda: panel.show_transcript(msgs))
        combined = " ".join(written)

        assert "dim" in combined, f"[dim] markup missing: {written}"
        assert "[tool: bash]" in combined, f"Tool content missing: {written}"


# ---------------------------------------------------------------------------
# New tests: show_task_and_messages and append_messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_task_and_messages_with_all_sections() -> None:
    """show_task_and_messages writes task header, messages, and report footer."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        task = FakeMessage("user", "Build the feature", "09:00")
        messages = [
            FakeMessage("user", "Hello", "09:01"),
            FakeMessage("assistant", "Working on it", "09:02"),
        ]
        report = FakeMessage("assistant", "Done! Feature complete.", "09:10")

        written = _capture_writes(
            panel, lambda: panel.show_task_and_messages(task, messages, report)
        )
        combined = " ".join(written)

        # Task section
        assert "📋 TASK" in combined, f"Task header missing: {written}"
        assert "Build the feature" in combined, f"Task content missing: {written}"
        assert "bold yellow" in combined, f"Task yellow styling missing: {written}"

        # Messages
        assert "Hello" in combined, f"User message missing: {written}"
        assert "Working on it" in combined, f"Assistant message missing: {written}"

        # Report section
        assert "📊 REPORT" in combined, f"Report header missing: {written}"
        assert "Done! Feature complete." in combined, f"Report content missing: {written}"
        assert "bold magenta" in combined, f"Report magenta styling missing: {written}"


@pytest.mark.asyncio
async def test_show_task_and_messages_without_task() -> None:
    """show_task_and_messages with task=None should skip the task section."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        messages = [FakeMessage("user", "Hello", "09:01")]
        report = FakeMessage("assistant", "Done.", "09:10")

        written = _capture_writes(
            panel, lambda: panel.show_task_and_messages(None, messages, report)
        )
        combined = " ".join(written)

        assert "📋 TASK" not in combined, f"Task header should be absent: {written}"
        assert "Hello" in combined, f"User message should be present: {written}"
        assert "📊 REPORT" in combined, f"Report header should be present: {written}"


@pytest.mark.asyncio
async def test_show_task_and_messages_without_report() -> None:
    """show_task_and_messages with report=None should skip the report section."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        task = FakeMessage("user", "Do something", "09:00")
        messages = [FakeMessage("assistant", "OK", "09:01")]

        written = _capture_writes(
            panel, lambda: panel.show_task_and_messages(task, messages, None)
        )
        combined = " ".join(written)

        assert "📋 TASK" in combined, f"Task header should be present: {written}"
        assert "Do something" in combined, f"Task content should be present: {written}"
        assert "OK" in combined, f"Message should be present: {written}"
        assert "📊 REPORT" not in combined, f"Report header should be absent: {written}"


@pytest.mark.asyncio
async def test_show_task_and_messages_empty_messages() -> None:
    """show_task_and_messages with empty messages list shows 'No messages yet'."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        task = FakeMessage("user", "Do something", "09:00")

        written = _capture_writes(
            panel, lambda: panel.show_task_and_messages(task, [], None)
        )
        combined = " ".join(written)

        assert "No messages yet" in combined, f"Expected 'No messages yet': {written}"


@pytest.mark.asyncio
async def test_append_messages_adds_without_clearing() -> None:
    """append_messages adds messages to existing content without clearing."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = app.query_one(LogPanel)

        first_writes: list[str] = []
        append_writes: list[str] = []

        def _fake_write_first(content, **kwargs):
            first_writes.append(str(content))

        def _fake_write_append(content, **kwargs):
            append_writes.append(str(content))

        # First, show some messages
        msgs_initial = [FakeMessage("user", "Initial message", "09:00")]
        with patch.object(panel, "write", side_effect=_fake_write_first):
            panel.show_task_and_messages(None, msgs_initial, None)

        # Now append new messages — no clear() should happen
        cleared = []
        original_clear = panel.clear

        def _fake_clear():
            cleared.append(True)
            original_clear()

        new_msgs = [FakeMessage("assistant", "New response", "09:05")]
        with patch.object(panel, "write", side_effect=_fake_write_append):
            with patch.object(panel, "clear", side_effect=_fake_clear):
                panel.append_messages(new_msgs)

        # clear() should NOT have been called
        assert len(cleared) == 0, "append_messages should not call clear()"

        # New message content should have been written
        combined_append = " ".join(append_writes)
        assert "New response" in combined_append, f"Appended message missing: {append_writes}"
        assert "bold green" in combined_append, f"Assistant styling missing: {append_writes}"
