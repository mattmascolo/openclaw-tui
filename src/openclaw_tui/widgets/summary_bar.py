"""SummaryBar — footer Static widget showing aggregate session counts."""
from __future__ import annotations

from textual.timer import Timer
from textual.widgets import Static

from ..models import AgentNode, SessionStatus


class SummaryBar(Static):
    """Footer widget showing aggregate session counts with Hearth palette.

    Displays: "● 3 active  ○ 5 idle  ⚠ 1 aborted  │ 9 total"
    Shows "⚡ Connecting..." when no data has been received yet.
    Shows "⚠ Gateway unreachable" on connection error.

    Animated spinner cycles while active sessions exist.

    The current display text is always stored in ``_display_text`` for easy
    introspection in tests.
    """

    _RUNNING_FRAMES = ("◐", "◓", "◑", "◒")

    DEFAULT_CSS = """
    SummaryBar {
        height: 3;
        background: #16213E;
        color: #FFF8E7;
        border-top: solid #2A2E3D;
        padding: 0 2;
    }
    """

    def __init__(self, content: str = "⚡ Connecting...", **kwargs: object) -> None:
        """Initialise the widget and capture the initial display text.

        Args:
            content: Initial text to display (default: connecting indicator).
            **kwargs: Forwarded to :class:`textual.widgets.Static`.
        """
        super().__init__(content, **kwargs)
        self._display_text: str = str(content)
        self._running_frame_index: int = 0
        self._active_count: int = 0
        self._anim_timer: Timer | None = None

    def on_mount(self) -> None:
        """Start spinner animation timer."""
        self._anim_timer = self.set_interval(0.18, self._animate_spinner)

    def on_unmount(self) -> None:
        """Stop animation timer when widget is removed."""
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer = None

    def update_summary(self, nodes: list[AgentNode], now_ms: int) -> None:
        """Count sessions by status across all nodes and update display text.

        Args:
            nodes:  List of AgentNode objects to summarise.
            now_ms: Current time in milliseconds (used to compute session status).
        """
        counts: dict[SessionStatus, int] = {s: 0 for s in SessionStatus}
        for agent_node in nodes:
            for session in agent_node.sessions:
                counts[session.status(now_ms)] += 1

        self._active_count = counts[SessionStatus.ACTIVE]
        total = sum(counts.values())
        text = self._render_counts(counts, total)
        self._display_text = text
        self.update(text)

    def _render_counts(self, counts: dict[SessionStatus, int], total: int) -> str:
        """Render counts with Hearth palette Rich markup."""
        active = counts[SessionStatus.ACTIVE]
        idle = counts[SessionStatus.IDLE]
        aborted = counts[SessionStatus.ABORTED]

        if active > 0:
            frame = self._RUNNING_FRAMES[self._running_frame_index % len(self._RUNNING_FRAMES)]
            self._running_frame_index += 1
            active_icon = f"[bold #F5A623]{frame}[/]"
        else:
            active_icon = "[bold #F5A623]●[/]"

        return (
            f"{active_icon} {active} active  "
            f"[dim #A8B5A2]○[/] {idle} idle  "
            f"[bold #C67B5C]⚠[/] {aborted} aborted  "
            f"[dim #7B7F87]│[/] [dim]{total} total[/dim]"
        )

    def _animate_spinner(self) -> None:
        """Advance spinner frame while active sessions exist."""
        if self._active_count <= 0:
            return
        # Re-render with next frame
        self.update(self._display_text)

    def set_error(self, message: str) -> None:
        """Display an error state in the summary bar.

        Args:
            message: Human-readable error description.
        """
        text = f"[bold #C67B5C]⚠[/] {message}"
        self._display_text = text
        self.update(text)
