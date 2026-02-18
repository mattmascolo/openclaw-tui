"""LogPanel widget — right-side transcript viewer for selected sessions."""
from __future__ import annotations

from textual.widgets import RichLog


class LogPanel(RichLog):
    """Right-side panel showing transcript messages for selected session.

    Default state: shows placeholder text "Select a session to view logs"
    When populated: shows messages as "[HH:MM] role: content"
    """

    DEFAULT_CSS = """
    LogPanel {
        border-left: solid $accent;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("markup", True)
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        """Show placeholder text when widget is first mounted."""
        self.show_placeholder()

    def show_transcript(self, messages: list) -> None:
        """Clear log and write formatted messages.

        Each message has: .timestamp (str, "HH:MM"), .role (str), .content (str)
        Format: "\\[HH:MM] role: content"  (square brackets escaped for Rich)
        Color coding via Rich markup:
        - user: [bold cyan]user[/]: content
        - assistant: [bold green]assistant[/]: content
        - tool: [dim]tool: content[/]
        """
        self.clear()
        if not messages:
            self.write("[dim]No messages found[/dim]")
            return
        for msg in messages:
            if msg.role == "user":
                self.write(f"[bold cyan]\\[{msg.timestamp}] user:[/bold cyan] {msg.content}")
            elif msg.role == "assistant":
                self.write(f"[bold green]\\[{msg.timestamp}] assistant:[/bold green] {msg.content}")
            else:
                self.write(f"[dim]\\[{msg.timestamp}] {msg.role}: {msg.content}[/dim]")

    def show_task_and_messages(
        self,
        task: object | None,
        messages: list,
        report: object | None,
    ) -> None:
        """Display task header, messages, and report footer.

        Layout:
        ┌────────────────────────────┐
        │ 📋 TASK                    │  (only if task is not None)
        │ <task content>             │
        │ ─────────────              │
        │ [21:44] user: message...   │  (regular messages)
        │ [21:44] assistant: resp... │
        │ [21:45] tool: [exec]       │
        │ ─────────────              │
        │ 📊 REPORT                  │  (only if report is not None)
        │ <report content>           │
        └────────────────────────────┘

        Uses Rich markup:
        - Task header: [bold yellow]📋 TASK[/bold yellow]
        - Task content: [yellow]{content}[/yellow]
        - Separator: [dim]{'─' * 40}[/dim]
        - Messages: same formatting as show_transcript
        - Report header: [bold magenta]📊 REPORT[/bold magenta]
        - Report content: [magenta]{content}[/magenta]
        """
        self.clear()

        if task is not None:
            self.write("[bold yellow]📋 TASK[/bold yellow]")
            self.write(f"[yellow]{task.content}[/yellow]")
            self.write(f"[dim]{'─' * 40}[/dim]")

        if not messages:
            self.write("[dim]No messages yet[/dim]")
        else:
            for msg in messages:
                if msg.role == "user":
                    self.write(f"[bold cyan]\\[{msg.timestamp}] user:[/bold cyan] {msg.content}")
                elif msg.role == "assistant":
                    self.write(f"[bold green]\\[{msg.timestamp}] assistant:[/bold green] {msg.content}")
                else:
                    self.write(f"[dim]\\[{msg.timestamp}] {msg.role}: {msg.content}[/dim]")

        if report is not None:
            self.write(f"[dim]{'─' * 40}[/dim]")
            self.write("[bold magenta]📊 REPORT[/bold magenta]")
            self.write(f"[magenta]{report.content}[/magenta]")

    def append_messages(self, messages: list) -> None:
        """Append new messages without clearing. For live streaming.

        Same formatting as regular messages in show_transcript/show_task_and_messages.
        Square brackets in timestamps are escaped for Rich.
        """
        for msg in messages:
            if msg.role == "user":
                self.write(f"[bold cyan]\\[{msg.timestamp}] user:[/bold cyan] {msg.content}")
            elif msg.role == "assistant":
                self.write(f"[bold green]\\[{msg.timestamp}] assistant:[/bold green] {msg.content}")
            else:
                self.write(f"[dim]\\[{msg.timestamp}] {msg.role}: {msg.content}[/dim]")

    def show_placeholder(self) -> None:
        """Show placeholder text."""
        self.clear()
        self.write("[dim]Select a session to view logs[/dim]")

    def show_error(self, message: str) -> None:
        """Show error message."""
        self.clear()
        self.write(f"[bold red]Error:[/bold red] {message}")
