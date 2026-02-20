"""Tests for AgentTreeWidget and SummaryBar widgets."""
from __future__ import annotations

import time

import pytest

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from openclaw_tui.models import AgentNode, SessionInfo, SessionStatus
from openclaw_tui.widgets import AgentTreeWidget, SummaryBar


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

NOW_MS = int(time.time() * 1000)


def make_session(
    key: str = "agent:main:test",
    kind: str = "agent",
    display_name: str = "test-session",
    label: str | None = None,
    model: str = "claude-opus-4-6",
    total_tokens: int = 27_652,
    context_tokens: int | None = None,
    aborted: bool = False,
    active: bool = True,
) -> SessionInfo:
    updated_at = NOW_MS - (5_000 if active else 120_000)
    return SessionInfo(
        key=key,
        kind=kind,
        channel="webchat",
        display_name=display_name,
        label=label,
        updated_at=updated_at,
        session_id="sess-abc123",
        model=model,
        context_tokens=context_tokens,
        total_tokens=total_tokens,
        aborted_last_run=aborted,
    )


class WidgetTestApp(App[None]):
    """Minimal host app for widget tests."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield AgentTreeWidget("Agents")
        yield SummaryBar("⚡ Connecting...")
        yield Footer()


# ---------------------------------------------------------------------------
# AgentTreeWidget tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tree_renders_agent_group_headers() -> None:
    """After update_tree, agent IDs appear as top-level group headers."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)
        nodes = [
            AgentNode(agent_id="main", sessions=[make_session()]),
            AgentNode(agent_id="sonnet-worker", sessions=[make_session(active=False)]),
        ]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        child_labels = [child.label.plain for child in tree.root.children]
        assert "main" in child_labels
        assert "sonnet-worker" in child_labels


@pytest.mark.asyncio
async def test_tree_renders_session_lines_with_status_icons() -> None:
    """Session branch nodes include status icon + channel icon + name; meta leaf has model + tokens + time."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        # Active session with label
        session = make_session(
            label="my-session",
            model="claude-opus-4-6",
            total_tokens=27_652,
            active=True,
        )
        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        # Session is now a branch node; meta is its leaf child
        agent_group = tree.root.children[0]
        session_branch = agent_group.children[0]
        name_text = session_branch.label.plain
        meta_leaf = session_branch.children[0]
        meta_text = meta_leaf.label.plain

        assert "●" in name_text           # active icon (markup stripped by .plain)
        assert "🌐" in name_text           # channel icon for webchat
        assert "my-session" in name_text   # label used (not display_name)
        assert "opus-4-6" in meta_text     # short_model in meta line
        assert "27K" in meta_text          # token count in meta line
        assert "active" in meta_text       # relative time


@pytest.mark.asyncio
async def test_tree_uses_display_name_when_no_label() -> None:
    """When label is None, display_name is used in session name line."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        session = make_session(
            display_name="subagent:abc123",
            label=None,
            total_tokens=0,
            active=True,
        )
        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        agent_group = tree.root.children[0]
        session_branch = agent_group.children[0]
        name_text = session_branch.label.plain
        meta_text = session_branch.children[0].label.plain

        assert "subagent:abc123" in name_text
        assert "0 tokens" in meta_text
        assert "active" in meta_text  # relative time


@pytest.mark.asyncio
async def test_tree_handles_empty_node_list() -> None:
    """Empty node list shows a 'No sessions' placeholder leaf."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)
        tree.update_tree([], NOW_MS)
        await pilot.pause()

        child_labels = [child.label.plain for child in tree.root.children]
        assert any("No sessions" in lbl for lbl in child_labels)


@pytest.mark.asyncio
async def test_tree_shows_aborted_icon() -> None:
    """Aborted sessions display the ⚠ icon."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        session = make_session(aborted=True, total_tokens=0)
        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        agent_group = tree.root.children[0]
        session_branch = agent_group.children[0]
        assert "⚠" in session_branch.label.plain


@pytest.mark.asyncio
async def test_tree_shows_idle_icon() -> None:
    """Idle sessions (updated > 30s ago) display the ○ icon."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        session = make_session(active=False)  # updated 120s ago → IDLE
        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        agent_group = tree.root.children[0]
        session_branch = agent_group.children[0]
        assert "○" in session_branch.label.plain


@pytest.mark.asyncio
async def test_tree_million_token_format() -> None:
    """Token counts ≥ 1M formatted as '1.2M' in meta line."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        session = make_session(total_tokens=1_200_000, active=True)
        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        agent_group = tree.root.children[0]
        session_branch = agent_group.children[0]
        meta_text = session_branch.children[0].label.plain
        assert "1.2M" in meta_text
        assert "active" in meta_text  # relative time


@pytest.mark.asyncio
async def test_tree_preserves_expansion_state() -> None:
    """Agent group expansion state is preserved across update_tree calls."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        session = make_session()
        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        # Collapse the group
        agent_group = tree.root.children[0]
        agent_group.collapse()
        await pilot.pause()
        assert not agent_group.is_expanded

        # Re-run update — collapsed state should be preserved
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        refreshed_group = tree.root.children[0]
        assert not refreshed_group.is_expanded


# ---------------------------------------------------------------------------
# SummaryBar tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_bar_initial_state() -> None:
    """SummaryBar shows '⚡ Connecting...' on startup."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        bar = app.query_one(SummaryBar)
        assert "⚡ Connecting..." in bar._display_text


@pytest.mark.asyncio
async def test_summary_bar_shows_correct_counts() -> None:
    """update_summary counts sessions by status correctly."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        bar = app.query_one(SummaryBar)

        # 2 active (recent), 1 idle (old), 1 aborted
        active_session_1 = make_session(key="a:main:s1", active=True)
        active_session_2 = make_session(key="a:main:s2", active=True)
        idle_session = make_session(key="a:main:s3", active=False)
        aborted_session = make_session(key="a:main:s4", aborted=True)

        nodes = [
            AgentNode(agent_id="main", sessions=[active_session_1, active_session_2]),
            AgentNode(agent_id="worker", sessions=[idle_session, aborted_session]),
        ]
        bar.update_summary(nodes, NOW_MS)
        await pilot.pause()

        text = bar._display_text
        assert "2 active" in text
        assert "1 idle" in text
        assert "1 aborted" in text
        assert "4 total" in text


@pytest.mark.asyncio
async def test_summary_bar_set_error() -> None:
    """set_error displays error message with ⚠ icon."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        bar = app.query_one(SummaryBar)
        bar.set_error("Gateway unreachable")
        await pilot.pause()

        assert "⚠" in bar._display_text
        assert "Gateway unreachable" in bar._display_text


@pytest.mark.asyncio
async def test_summary_bar_zero_sessions() -> None:
    """Empty node list shows zero counts."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        bar = app.query_one(SummaryBar)
        bar.update_summary([], NOW_MS)
        await pilot.pause()

        text = bar._display_text
        assert "0 active" in text
        assert "0 total" in text


# ---------------------------------------------------------------------------
# New tests: _session_label snippet support + update_tree with snippets
# ---------------------------------------------------------------------------


def test_session_label_without_snippet() -> None:
    """_session_label without snippet returns base format unchanged."""
    from openclaw_tui.widgets.agent_tree import _session_label

    session = make_session(label="my-session", model="claude-opus-4-6", total_tokens=27_652, active=True)
    label = _session_label(session, NOW_MS)

    assert "my-session" in label
    assert "opus-4-6" in label
    assert "27K" in label
    assert "tokens" in label
    # Should NOT contain a snippet
    assert "—" not in label


def test_session_label_with_snippet() -> None:
    """_session_label with snippet appends snippet after tokens."""
    from openclaw_tui.widgets.agent_tree import _session_label

    session = make_session(label="my-session", model="claude-opus-4-6", total_tokens=27_652, active=True)
    label = _session_label(session, NOW_MS, snippet="Both builders spawned...")

    assert "my-session" in label
    assert "27K" in label
    assert "—" in label
    assert "Both builders spawned..." in label


@pytest.mark.asyncio
async def test_tree_update_with_snippets_dict() -> None:
    """update_tree with snippets dict includes snippet in meta leaf label."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        session = make_session(
            key="agent:main:sess-xyz",
            label="my-session",
            active=True,
        )
        # Fake session_id is "sess-abc123" from make_session
        snippets = {"sess-abc123": "Working on task..."}

        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS, snippets=snippets)
        await pilot.pause()

        agent_group = tree.root.children[0]
        session_branch = agent_group.children[0]
        name_text = session_branch.label.plain
        meta_text = session_branch.children[0].label.plain

        assert "my-session" in name_text
        assert "Working on task..." in meta_text
        assert "active" in meta_text  # relative time


# ---------------------------------------------------------------------------
# New: relative_time + channel icon tests
# ---------------------------------------------------------------------------


def test_relative_time_active() -> None:
    """Timestamps within 30s return 'active'."""
    from openclaw_tui.utils.time import relative_time

    assert relative_time(NOW_MS - 5_000, NOW_MS) == "active"
    assert relative_time(NOW_MS, NOW_MS) == "active"
    assert relative_time(NOW_MS + 1_000, NOW_MS) == "active"  # future → active


def test_relative_time_seconds() -> None:
    """31–59 seconds returns 'Xs ago'."""
    from openclaw_tui.utils.time import relative_time

    assert relative_time(NOW_MS - 45_000, NOW_MS) == "45s ago"


def test_relative_time_minutes() -> None:
    """60s–59m returns 'Xm ago'."""
    from openclaw_tui.utils.time import relative_time

    assert relative_time(NOW_MS - 180_000, NOW_MS) == "3m ago"


def test_relative_time_hours() -> None:
    """1h–23h returns 'Xh ago'."""
    from openclaw_tui.utils.time import relative_time

    assert relative_time(NOW_MS - 7_200_000, NOW_MS) == "2h ago"


def test_relative_time_days() -> None:
    """24h+ returns 'Xd ago'."""
    from openclaw_tui.utils.time import relative_time

    assert relative_time(NOW_MS - 172_800_000, NOW_MS) == "2d ago"


def test_channel_icon_exact_match() -> None:
    """Known channels return their icon."""
    from openclaw_tui.widgets.agent_tree import _channel_icon

    assert _channel_icon("discord") == "⌨"
    assert _channel_icon("webchat") == "🌐"
    assert _channel_icon("cron") == "⏱"


def test_channel_icon_substring_match() -> None:
    """Channel names containing a known key match via substring."""
    from openclaw_tui.widgets.agent_tree import _channel_icon

    assert _channel_icon("cron:nightly-job") == "⏱"


def test_channel_icon_unknown_fallback() -> None:
    """Unknown channels fall back to middle dot."""
    from openclaw_tui.widgets.agent_tree import _channel_icon

    assert _channel_icon("carrier-pigeon") == "·"


@pytest.mark.asyncio
async def test_tree_shows_channel_icon() -> None:
    """Session name lines include channel icon."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        session = make_session(label="my-session", active=True)
        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        agent_group = tree.root.children[0]
        session_branch = agent_group.children[0]
        name_text = session_branch.label.plain
        assert "🌐" in name_text  # webchat channel icon
