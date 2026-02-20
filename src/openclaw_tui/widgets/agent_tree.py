"""AgentTreeWidget — Textual Tree widget displaying agents and their sessions."""
from __future__ import annotations

import re

from textual.widgets import Tree

from ..models import AgentNode, SessionInfo, SessionStatus, STATUS_ICONS, STATUS_MARKUP
from ..utils.time import relative_time


def _format_tokens(count: int) -> str:
    """Format token count as human-readable string.

    Examples:
        0       → "0"
        27652   → "27K"
        1200000 → "1.2M"
    """
    if count == 0:
        return "0"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count // 1_000}K"
    return str(count)


# ---------------------------------------------------------------------------
# Channel icons
# ---------------------------------------------------------------------------

_CHANNEL_ICONS: dict[str, str] = {
    "discord": "⌨",
    "cron": "⏱",
    "webchat": "🌐",
    "signal": "📶",
    "telegram": "✈",
}


def _channel_icon(channel: str) -> str:
    """Return the icon for a channel. Exact match first, then substring.

    Handles names like 'cron:nightly-job' by substring matching 'cron'.
    Unknown channels fall back to '·' (middle dot).
    """
    if channel in _CHANNEL_ICONS:
        return _CHANNEL_ICONS[channel]
    for key, icon in _CHANNEL_ICONS.items():
        if key in channel:
            return icon
    return "·"


# Snippets that add no value — filter them out
_JUNK_SNIPPETS = frozenset({
    "NO_REPLY",
    "HEARTBEAT_OK",
    "(no output recorded)",
    "",
})


def _clean_display_name(session: SessionInfo) -> str:
    """Return a clean, human-readable name for a session.

    Transformations:
      - webchat:g-agent-main-main → webchat
      - discord:g-123456789 → discord DM
      - discord:123456789#general → #general
      - Labels (Cron: Nightly, forge-builder-data, etc.) pass through as-is
    """
    # Prefer label if set
    if session.label is not None:
        return session.label

    name = session.display_name

    # discord:GUILD#channel → #channel
    match = re.match(r"discord:\d+#(.+)", name)
    if match:
        return f"#{match.group(1)}"

    # discord:g-DIGITS → discord (last 4 digits to differentiate)
    match = re.match(r"discord:g-(\d+)", name)
    if match:
        short_id = match.group(1)[-4:]
        return f"discord …{short_id}"

    # webchat:g-agent-main-main → webchat
    if name.startswith("webchat:"):
        return "webchat"

    return name


def _session_name_label(session: SessionInfo, now_ms: int) -> str:
    """First line: colored status icon + channel icon + clean name.

    Format: "[bold #F5A623]●[/] 🌐 webchat"
    Uses Rich markup for Hearth palette colors.
    """
    icon = STATUS_MARKUP[session.status(now_ms)]
    chan = _channel_icon(session.channel)
    name = _clean_display_name(session)
    return f"{icon} {chan} {name}"


def _session_meta_label(
    session: SessionInfo,
    now_ms: int,
    snippet: str | None = None,
) -> str:
    """Second line: model · tokens · relative time · snippet (if any).

    Format: "opus-4-6 · 28K tokens · active"
    With snippet: "opus-4-6 · 28K tokens · 3m ago · \"Nightly consolidation...\""
    """
    model = session.short_model
    tokens = _format_tokens(session.total_tokens)
    rel = relative_time(session.updated_at, now_ms)
    meta = f"{model} · {tokens} tokens · {rel}"

    if snippet and snippet.strip() not in _JUNK_SNIPPETS:
        clean = snippet.strip().replace("\n", " ")[:40]
        meta += f" · \"{clean}\""

    return meta


# Keep the old function signature for backward compat with tests
def _session_label(session: SessionInfo, now_ms: int, snippet: str | None = None) -> str:
    """Build a combined single-line label (used by tests, legacy compat).

    Format: "● webchat (opus-4-6) 27K tokens"
    """
    status = session.status(now_ms)
    icon = STATUS_ICONS[status]
    name = _clean_display_name(session)
    model = session.short_model
    tokens = _format_tokens(session.total_tokens)
    base = f"{icon} {name} ({model}) {tokens} tokens"
    if snippet and snippet.strip() not in _JUNK_SNIPPETS:
        clean = snippet.strip().replace("\n", " ")[:40]
        return f'{base} — "{clean}"'
    return base


class AgentTreeWidget(Tree[SessionInfo]):
    """Tree widget displaying agents and their sessions.

    Two-line nested layout per session with Hearth palette colors:
        ▼ main
          ▼ [amber]●[/] 🌐 webchat
              opus-4-6 · 0 tokens · active
          ▼ [sage]○[/] ⏱ Cron: Nightly Consolidation
              opus-4-6 · 28K tokens · 3h ago · "Nightly consolidation..."
    """

    def on_mount(self) -> None:
        """Hide root node; ensure it is expanded so children are visible."""
        self.show_root = False
        self.root.expand()

    def update_tree(
        self,
        nodes: list[AgentNode],
        now_ms: int,
        snippets: dict[str, str] | None = None,
    ) -> None:
        """Rebuild tree from agent nodes with nested session layout.

        Each session becomes a branch node (name line) with a leaf child (meta line).
        The SessionInfo data is set on the branch node so selection still works.

        Preserves expansion state of agent groups.
        """
        # Snapshot expansion state: agent groups + individual sessions
        expanded_groups: dict[str, bool] = {}
        expanded_sessions: dict[str, bool] = {}
        for child in self.root.children:
            expanded_groups[child.label.plain] = child.is_expanded
            for session_node in child.children:
                if session_node.data is not None:
                    expanded_sessions[session_node.data.session_id] = session_node.is_expanded

        self.clear()
        self.root.expand()

        if not nodes:
            self.root.add_leaf("No sessions")
            return

        for agent_node in nodes:
            was_group_expanded = expanded_groups.get(agent_node.agent_id, True)
            group = self.root.add(
                agent_node.agent_id,
                expand=was_group_expanded,
            )
            for session in agent_node.sessions:
                snip = snippets.get(session.session_id) if snippets else None
                name_label = _session_name_label(session, now_ms)
                meta_label = _session_meta_label(session, now_ms, snippet=snip)

                # Session is a branch node with data, meta is a leaf child
                was_session_expanded = expanded_sessions.get(session.session_id, False)
                session_branch = group.add(name_label, data=session, expand=was_session_expanded)
                session_branch.add_leaf(meta_label)
