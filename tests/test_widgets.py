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
    """Session leaf nodes include status icon, name, model, and token count."""
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

        # Get the session leaf under "main"
        agent_group = tree.root.children[0]
        leaf = agent_group.children[0]
        label_text = leaf.label.plain

        assert "●" in label_text          # active icon
        assert "my-session" in label_text # label used (not display_name)
        assert "opus-4-6" in label_text   # short_model
        assert "27K" in label_text        # token count formatted


@pytest.mark.asyncio
async def test_tree_uses_display_name_when_no_label() -> None:
    """When label is None, display_name is used in session line."""
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
        leaf = agent_group.children[0]
        label_text = leaf.label.plain

        assert "subagent:abc123" in label_text
        assert "0" in label_text  # zero tokens


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
        leaf = agent_group.children[0]
        assert "⚠" in leaf.label.plain


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
        leaf = agent_group.children[0]
        assert "○" in leaf.label.plain


@pytest.mark.asyncio
async def test_tree_million_token_format() -> None:
    """Token counts ≥ 1M formatted as '1.2M'."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(AgentTreeWidget)

        session = make_session(total_tokens=1_200_000, active=True)
        nodes = [AgentNode(agent_id="main", sessions=[session])]
        tree.update_tree(nodes, NOW_MS)
        await pilot.pause()

        agent_group = tree.root.children[0]
        leaf = agent_group.children[0]
        assert "1.2M" in leaf.label.plain


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
        assert "Active: 2" in text
        assert "Idle: 1" in text
        assert "Aborted: 1" in text
        assert "Total: 4" in text


@pytest.mark.asyncio
async def test_summary_bar_set_error() -> None:
    """set_error displays error message prefixed with ❌."""
    app = WidgetTestApp()
    async with app.run_test() as pilot:
        bar = app.query_one(SummaryBar)
        bar.set_error("Gateway unreachable")
        await pilot.pause()

        assert "❌" in bar._display_text
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
        assert "Active: 0" in text
        assert "Total: 0" in text


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
    """update_tree with snippets dict includes snippet in session leaf label."""
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
        leaf = agent_group.children[0]
        label_text = leaf.label.plain

        assert "my-session" in label_text
        assert "Working on task..." in label_text
