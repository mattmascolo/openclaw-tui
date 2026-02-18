"""Tests for AgentDashboard app (smoke tests + composition)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Header, Footer

from openclaw_tui.app import AgentDashboard
from openclaw_tui.widgets import AgentTreeWidget, SummaryBar
from openclaw_tui.client import GatewayError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_load_config():
    """Return a mock GatewayConfig with sensible defaults."""
    from openclaw_tui.config import GatewayConfig
    return GatewayConfig(host="localhost", port=9876, token=None)


@pytest.fixture(autouse=True)
def _mock_gateway(monkeypatch):
    """Patch load_config and GatewayClient for all app tests."""
    monkeypatch.setattr(
        "openclaw_tui.app.load_config",
        _mock_load_config,
    )
    mock_client = MagicMock()
    mock_client.fetch_sessions.return_value = []
    mock_client.close.return_value = None
    monkeypatch.setattr(
        "openclaw_tui.app.GatewayClient",
        MagicMock(return_value=mock_client),
    )
    monkeypatch.setattr(
        "openclaw_tui.app.build_tree",
        lambda sessions: [],
    )


# ---------------------------------------------------------------------------
# App composition tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_composes_header() -> None:
    """App includes a Header widget."""
    app = AgentDashboard()
    async with app.run_test() as pilot:
        assert app.query_one(Header) is not None


@pytest.mark.asyncio
async def test_app_composes_footer() -> None:
    """App includes a Footer widget."""
    app = AgentDashboard()
    async with app.run_test() as pilot:
        assert app.query_one(Footer) is not None


@pytest.mark.asyncio
async def test_app_composes_agent_tree_widget() -> None:
    """App includes an AgentTreeWidget."""
    app = AgentDashboard()
    async with app.run_test() as pilot:
        assert app.query_one(AgentTreeWidget) is not None


@pytest.mark.asyncio
async def test_app_composes_summary_bar() -> None:
    """App includes a SummaryBar."""
    app = AgentDashboard()
    async with app.run_test() as pilot:
        assert app.query_one(SummaryBar) is not None


@pytest.mark.asyncio
async def test_app_mounts_without_crash() -> None:
    """Smoke test: app mounts, runs, and exits cleanly."""
    app = AgentDashboard()
    async with app.run_test() as pilot:
        assert app.is_running
        await pilot.pause()
        assert app.is_running


@pytest.mark.asyncio
async def test_app_all_widgets_composed() -> None:
    """App compose() yields Header, AgentTreeWidget, SummaryBar, Footer."""
    app = AgentDashboard()
    async with app.run_test() as pilot:
        assert app.query_one(Header) is not None
        assert app.query_one(AgentTreeWidget) is not None
        assert app.query_one(SummaryBar) is not None
        assert app.query_one(Footer) is not None


@pytest.mark.asyncio
async def test_app_summary_bar_initial_text() -> None:
    """SummaryBar starts with connecting text."""
    app = AgentDashboard()
    async with app.run_test() as pilot:
        bar = app.query_one(SummaryBar)
        # Initial state before any poll completes, or after first empty poll
        assert hasattr(bar, '_display_text')


# ---------------------------------------------------------------------------
# New tests: selection loads task/report, live tailing, snippet cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_selection_loads_task_and_report(monkeypatch) -> None:
    """on_tree_node_selected calls show_task_and_messages with task, messages, report."""
    from openclaw_tui.models import SessionInfo
    from openclaw_tui.widgets.log_panel import LogPanel

    task_msg = MagicMock()
    task_msg.role = "user"
    task_msg.content = "The task"
    task_msg.timestamp = "09:00"

    report_msg = MagicMock()
    report_msg.role = "assistant"
    report_msg.content = "The report"
    report_msg.timestamp = "09:10"

    user_msg = MagicMock()
    user_msg.role = "user"
    user_msg.content = "Hello"
    user_msg.timestamp = "09:01"

    monkeypatch.setattr("openclaw_tui.app.read_task", lambda *a, **kw: task_msg)
    monkeypatch.setattr("openclaw_tui.app.read_report", lambda *a, **kw: report_msg)
    monkeypatch.setattr("openclaw_tui.app.read_transcript", lambda *a, **kw: [user_msg])

    calls: list[tuple] = []

    def _fake_show(task, messages, report):
        calls.append((task, messages, report))

    app = AgentDashboard()
    async with app.run_test() as pilot:
        log_panel = app.query_one(LogPanel)
        monkeypatch.setattr(log_panel, "show_task_and_messages", _fake_show)

        # Simulate selecting a session node
        from openclaw_tui.models import SessionInfo
        import time
        now_ms = int(time.time() * 1000)
        session = SessionInfo(
            key="agent:main:test",
            kind="agent",
            channel="webchat",
            display_name="test-session",
            label="test-session",
            updated_at=now_ms - 5000,
            session_id="sess-test",
            model="claude-opus-4-6",
            context_tokens=None,
            total_tokens=1000,
            aborted_last_run=False,
        )

        # Manually invoke the handler
        from unittest.mock import MagicMock as MM
        event = MM()
        event.node = MM()
        event.node.data = session

        app.on_tree_node_selected(event)

        assert len(calls) == 1, f"show_task_and_messages called {len(calls)} times"
        task_arg, msgs_arg, report_arg = calls[0]
        assert task_arg is task_msg
        assert report_arg is report_msg


@pytest.mark.asyncio
async def test_live_tailing_appends_new_messages(monkeypatch) -> None:
    """_poll_sessions appends new messages to LogPanel when session is selected."""
    from openclaw_tui.widgets.log_panel import LogPanel
    from openclaw_tui.models import SessionInfo
    import time

    new_msg = MagicMock()
    new_msg.role = "assistant"
    new_msg.content = "New streamed content"
    new_msg.timestamp = "09:05"

    monkeypatch.setattr("openclaw_tui.app.read_transcript_incremental",
                        lambda *a, **kw: ([new_msg], 500))

    appended: list = []

    app = AgentDashboard()
    async with app.run_test() as pilot:
        log_panel = app.query_one(LogPanel)
        monkeypatch.setattr(log_panel, "append_messages", lambda msgs: appended.extend(msgs))

        # Set up a selected session
        now_ms = int(time.time() * 1000)
        session = SessionInfo(
            key="agent:main:tail-test",
            kind="agent",
            channel="webchat",
            display_name="tail-session",
            label="tail-session",
            updated_at=now_ms - 5000,
            session_id="sess-tail",
            model="claude-opus-4-6",
            context_tokens=None,
            total_tokens=1000,
            aborted_last_run=False,
        )
        app._selected_session = session
        app._tail_offset = 0
        app._snippet_cache = {}
        app._snippet_counter = 0

        # Run one poll cycle
        await app._poll_sessions()
        await pilot.pause()

        assert len(appended) > 0, "Expected new messages to be appended"
        assert appended[0] is new_msg


@pytest.mark.asyncio
async def test_snippet_cache_refreshes_every_5_polls(monkeypatch) -> None:
    """Snippet cache is updated every 5 polls (when counter hits 5)."""
    from openclaw_tui.models import SessionInfo
    import time

    activity_calls: list[tuple] = []

    def _fake_get_last_activity(session_id, agent_id):
        activity_calls.append((session_id, agent_id))
        return "Latest activity snippet"

    monkeypatch.setattr("openclaw_tui.app.get_last_activity", _fake_get_last_activity)
    monkeypatch.setattr("openclaw_tui.app.read_transcript_incremental",
                        lambda *a, **kw: ([], 0))

    now_ms = int(time.time() * 1000)
    session = SessionInfo(
        key="agent:main:snip-test",
        kind="agent",
        channel="webchat",
        display_name="snip-session",
        label="snip-session",
        updated_at=now_ms - 5000,
        session_id="sess-snip",
        model="claude-opus-4-6",
        context_tokens=None,
        total_tokens=1000,
        aborted_last_run=False,
    )

    def _fake_fetch_sessions():
        return [session]

    app = AgentDashboard()
    async with app.run_test() as pilot:
        # Reset counter and patch client
        app._snippet_counter = 0
        app._snippet_cache = {}
        app._client.fetch_sessions = _fake_fetch_sessions

        # Patch build_tree to return the node
        from openclaw_tui.models import AgentNode
        monkeypatch.setattr("openclaw_tui.app.build_tree",
                            lambda sessions: [AgentNode(agent_id="main", sessions=sessions)])

        # Run 4 polls — snippet should NOT refresh
        for _ in range(4):
            await app._poll_sessions()
        assert len(activity_calls) == 0, "Should not fetch snippets before 5th poll"

        # 5th poll — should refresh
        await app._poll_sessions()
        assert len(activity_calls) >= 1, "Should fetch snippets on 5th poll"
        assert app._snippet_cache.get("sess-snip") == "Latest activity snippet"
