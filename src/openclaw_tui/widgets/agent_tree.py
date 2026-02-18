"""AgentTreeWidget — Textual Tree widget displaying agents and their sessions."""
from __future__ import annotations

import re

from textual.widgets import Tree

from ..models import AgentNode, SessionInfo, SessionStatus, STATUS_ICONS, STATUS_STYLES


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

    # discord:g-DIGITS → discord DM
    if re.match(r"discord:g-\d+", name):
        return "discord DM"

    # webchat:g-agent-main-main → webchat
    if name.startswith("webchat:"):
        return "webchat"

    return name


def _session_name_label(session: SessionInfo, now_ms: int) -> str:
    """First line: status icon + clean name.

    Format: "● webchat" or "○ Cron: Nightly Consolidation"
    """
    status = session.status(now_ms)
    icon = STATUS_ICONS[status]
    name = _clean_display_name(session)
    return f"{icon} {name}"


def _session_meta_label(
    session: SessionInfo,
    snippet: str | None = None,
) -> str:
    """Second line: model · tokens · snippet (if any).

    Format: "opus-4-6 · 28K tokens"
    With snippet: "opus-4-6 · 28K tokens · \"Nightly consolidation...\""
    """
    model = session.short_model
    tokens = _format_tokens(session.total_tokens)
    meta = f"{model} · {tokens} tokens"

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

    Two-line nested layout per session:
        ▼ main
          ▼ ● webchat
              opus-4-6 · 0 tokens
          ▼ ○ Cron: Nightly Consolidation
              opus-4-6 · 28K tokens · "Nightly consolidation..."
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
                meta_label = _session_meta_label(session, snippet=snip)

                # Session is a branch node with data, meta is a leaf child
                was_session_expanded = expanded_sessions.get(session.session_id, False)
                session_branch = group.add(name_label, data=session, expand=was_session_expanded)
                session_branch.add_leaf(meta_label)
