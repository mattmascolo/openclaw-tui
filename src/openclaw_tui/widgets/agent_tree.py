"""AgentTreeWidget — Textual Tree widget displaying agents and their sessions."""
from __future__ import annotations

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


def _session_label(session: SessionInfo, now_ms: int, snippet: str | None = None) -> str:
    """Build the display label for a session leaf node.

    Format: "● my-session (opus-4-6) 27K tokens"
    With snippet: "● my-session (opus-4-6) 27K tokens — \"Both builders spawned...\""
    """
    status = session.status(now_ms)
    icon = STATUS_ICONS[status]
    name = session.label if session.label is not None else session.display_name
    model = session.short_model
    tokens = _format_tokens(session.total_tokens)
    base = f"{icon} {name} ({model}) {tokens} tokens"
    if snippet:
        # Truncate snippet and add in dimmed style (no Rich markup in Tree labels)
        return f'{base} — "{snippet}"'
    return base


class AgentTreeWidget(Tree[SessionInfo]):
    """Tree widget displaying agents and their sessions.

    Top-level nodes: agent IDs (e.g., "main", "sonnet-worker")
    Children: individual sessions with status icon, label/name, model, tokens

    Format per session line:
        "● my-session (opus-4-6) 27K tokens"
        "○ cron: Nightly Consolidation (sonnet-4-5) 30K tokens"
        "⚠ subagent:abc123 (minimax) 0 tokens"
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
        """Rebuild tree from agent nodes. Preserves expansion state of agent groups.

        Args:
            nodes:    List of AgentNode objects to display.
            now_ms:   Current time in milliseconds (used to compute session status).
            snippets: Optional mapping of session_id → last activity string.
        """
        # Snapshot current expansion state keyed by agent_id label text
        expanded: dict[str, bool] = {}
        for child in self.root.children:
            expanded[child.label.plain] = child.is_expanded

        self.clear()
        # Ensure root is expanded after clear (clear preserves the state, but be explicit)
        self.root.expand()

        if not nodes:
            self.root.add_leaf("No sessions")
            return

        for agent_node in nodes:
            was_expanded = expanded.get(agent_node.agent_id, True)
            group = self.root.add(
                agent_node.agent_id,
                expand=was_expanded,
            )
            for session in agent_node.sessions:
                snip = snippets.get(session.session_id) if snippets else None
                label = _session_label(session, now_ms, snippet=snip)
                group.add_leaf(label, data=session)
