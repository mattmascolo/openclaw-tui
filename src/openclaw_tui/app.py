"""AgentDashboard — main Textual TUI application with live polling."""
from __future__ import annotations

import asyncio
import logging
import time

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Tree
from textual.worker import Worker, WorkerState

from .widgets import AgentTreeWidget, SummaryBar, LogPanel
from .config import GatewayConfig, load_config
from .client import GatewayClient, GatewayError
from .tree import build_tree
from .transcript import (
    read_transcript,
    read_task,
    read_report,
    read_transcript_incremental,
    get_last_activity,
)

logger = logging.getLogger(__name__)


class AgentDashboard(App[None]):
    """Main TUI application with live-updating agent tree.

    Polls the OpenClaw gateway every 2 seconds, groups sessions into an
    agent tree, and displays them with a live summary footer.
    """

    TITLE = "OpenClaw Agent Dashboard"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "copy_info", "Copy Info"),
    ]

    CSS = """
    #main-content {
        height: 1fr;
    }
    AgentTreeWidget {
        width: 2fr;
    }
    LogPanel {
        width: 3fr;
        border-left: solid $accent;
    }
    SummaryBar {
        height: auto;
        min-height: 3;
        background: $surface;
        padding: 1;
        dock: bottom;
    }
    """

    def compose(self) -> ComposeResult:
        """Layout: Header → Horizontal(AgentTreeWidget + LogPanel) → SummaryBar → Footer."""
        yield Header()
        with Horizontal(id="main-content"):
            yield AgentTreeWidget("Agents")
            yield LogPanel()
        yield SummaryBar("⚡ Connecting...")
        yield Footer()

    def on_mount(self) -> None:
        """Load config, create client, start 2 s polling interval."""
        logger.info("AgentDashboard mounted — starting poll loop")
        self._config = load_config()
        self._client = GatewayClient(self._config)
        self._selected_session: SessionInfo | None = None
        self._tail_offset: int = 0
        self._snippet_cache: dict[str, str] = {}
        self._snippet_counter: int = 0
        self.set_interval(2.0, self._trigger_poll)
        self._trigger_poll()  # immediate first poll

    def _trigger_poll(self) -> None:
        """Trigger an exclusive worker to poll the gateway."""
        self.run_worker(self._poll_sessions, exclusive=True)

    async def _poll_sessions(self) -> None:
        """Worker coroutine: fetch sessions, build tree, update widgets.

        Runs ``fetch_sessions`` (sync httpx call) in a thread via
        ``asyncio.to_thread`` so the TUI event loop stays responsive.
        On any error, updates the SummaryBar with an error message instead
        of crashing.
        """
        now_ms = int(time.time() * 1000)
        try:
            sessions = await asyncio.to_thread(self._client.fetch_sessions)
            nodes = build_tree(sessions)

            # Refresh snippets every 5 polls (~10 seconds)
            self._snippet_counter += 1
            if self._snippet_counter >= 5:
                self._snippet_counter = 0
                snippets: dict[str, str] = {}
                for s in sessions:
                    activity = await asyncio.to_thread(
                        get_last_activity, s.session_id, s.agent_id
                    )
                    if activity:
                        snippets[s.session_id] = activity
                self._snippet_cache = snippets

            tree = self.query_one(AgentTreeWidget)
            bar = self.query_one(SummaryBar)
            tree.update_tree(nodes, now_ms, snippets=self._snippet_cache)
            bar.update_summary(nodes, now_ms)

            # Live tail the selected session
            if self._selected_session is not None:
                new_msgs, new_offset = await asyncio.to_thread(
                    read_transcript_incremental,
                    self._selected_session.session_id,
                    self._selected_session.agent_id,
                    self._tail_offset,
                )
                if new_msgs:
                    self._tail_offset = new_offset
                    log_panel = self.query_one(LogPanel)
                    log_panel.append_messages(new_msgs)

            logger.info("Poll OK — %d sessions across %d agents", len(sessions), len(nodes))
        except (GatewayError, ConnectionError) as exc:
            logger.warning("Gateway poll failed: %s", exc)
            self._show_poll_error(str(exc) or "Gateway unreachable")
        except Exception as exc:  # noqa: BLE001 — never crash the TUI
            logger.warning("Unexpected poll error: %s", exc)
            self._show_poll_error(str(exc) or "Unknown error")

    def _show_poll_error(self, message: str) -> None:
        """Update SummaryBar with error message (safe — never raises)."""
        try:
            bar = self.query_one(SummaryBar)
            bar.set_error(message)
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not update SummaryBar: %s", exc)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """When a session node is selected, show its transcript with task and report."""
        node_data = event.node.data  # This is the SessionInfo object (set in AgentTreeWidget)
        if node_data is None:
            return  # Agent group header, not a session
        self._selected_session = node_data
        log_panel = self.query_one(LogPanel)
        try:
            # Read task, full transcript, and report
            task = read_task(node_data.session_id, node_data.agent_id)
            report = read_report(node_data.session_id, node_data.agent_id)
            messages = read_transcript(node_data.session_id, node_data.agent_id, limit=50)
            log_panel.show_task_and_messages(task, messages, report)

            # Set tail offset to current file size for live streaming
            from pathlib import Path
            transcript_path = (
                Path.home()
                / ".openclaw"
                / "agents"
                / node_data.agent_id
                / "sessions"
                / f"{node_data.session_id}.jsonl"
            )
            self._tail_offset = transcript_path.stat().st_size if transcript_path.exists() else 0
        except Exception as exc:  # noqa: BLE001 — never crash the TUI
            logger.warning("Failed to load transcript for %s: %s", node_data.session_id, exc)
            log_panel.show_error(str(exc) or "Failed to load transcript")

    def action_copy_info(self) -> None:
        """Copy selected session info to clipboard."""
        session = getattr(self, "_selected_session", None)
        if session is None:
            self.notify("No session selected", severity="warning")
            return
        info_lines = [
            f"Agent: {session.agent_id}",
            f"Session: {session.key}",
            f"Name: {session.label or session.display_name}",
            f"Model: {session.model}",
            f"Tokens: {session.total_tokens}",
            f"Session ID: {session.session_id}",
        ]
        info_text = "\n".join(info_lines)
        try:
            import subprocess
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=info_text.encode(),
                capture_output=True,
                timeout=2,
            )
            if proc.returncode == 0:
                self.notify(f"Copied: {session.label or session.display_name}")
            else:
                # Fallback: try xsel
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=info_text.encode(),
                    capture_output=True,
                    timeout=2,
                )
                self.notify(f"Copied: {session.label or session.display_name}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # No clipboard tool available — write to /tmp instead
            import tempfile
            path = "/tmp/openclaw-tui-session.txt"
            with open(path, "w") as f:
                f.write(info_text)
            self.notify(f"Saved to {path} (install xclip for clipboard)")

    def action_refresh(self) -> None:
        """Manual refresh triggered by 'r' key."""
        logger.info("Manual refresh triggered")
        self._trigger_poll()

    def on_unmount(self) -> None:
        """Clean up HTTP client on exit."""
        if hasattr(self, "_client"):
            logger.info("Closing gateway client")
            self._client.close()
