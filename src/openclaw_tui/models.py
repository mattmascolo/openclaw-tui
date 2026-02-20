from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SessionStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    ABORTED = "aborted"


STATUS_ICONS: dict[SessionStatus, str] = {
    SessionStatus.ACTIVE: "●",
    SessionStatus.IDLE: "○",
    SessionStatus.ABORTED: "⚠",
}

STATUS_STYLES: dict[SessionStatus, str] = {
    SessionStatus.ACTIVE: "green",
    SessionStatus.IDLE: "dim",
    SessionStatus.ABORTED: "yellow",
}

# Rich markup status icons (Hearth palette)
STATUS_MARKUP: dict[SessionStatus, str] = {
    SessionStatus.ACTIVE: "[bold #F5A623]●[/]",
    SessionStatus.IDLE: "[dim #A8B5A2]○[/]",
    SessionStatus.ABORTED: "[bold #C67B5C]⚠[/]",
}


@dataclass
class SessionInfo:
    key: str
    kind: str
    channel: str
    display_name: str
    label: str | None
    updated_at: int
    session_id: str
    model: str
    context_tokens: int | None
    total_tokens: int
    aborted_last_run: bool

    def status(self, now_ms: int) -> SessionStatus:
        if self.aborted_last_run:
            return SessionStatus.ABORTED
        if (now_ms - self.updated_at) < 30_000:
            return SessionStatus.ACTIVE
        return SessionStatus.IDLE

    @property
    def short_model(self) -> str:
        name = self.model.replace("claude-", "")
        parts = name.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 8:
            name = parts[0]
        return name

    @property
    def context_label(self) -> str:
        parts = self.key.split(":", 2)
        return parts[2] if len(parts) >= 3 else self.key

    @property
    def agent_id(self) -> str:
        """Extract agent_id from key. 'agent:main:cron:UUID' → 'main'."""
        parts = self.key.split(":", 2)
        return parts[1] if len(parts) >= 2 else "unknown"


@dataclass
class AgentNode:
    agent_id: str
    sessions: list[SessionInfo] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.agent_id
