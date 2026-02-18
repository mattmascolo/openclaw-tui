from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import logging
import os

logger = logging.getLogger(__name__)

OPENCLAW_DIR = Path.home() / ".openclaw"


@dataclass
class TranscriptMessage:
    timestamp: str  # HH:MM format for display (extracted from ISO timestamp)
    role: str       # "user", "assistant", "tool"
    content: str    # Text content, truncated


def _extract_timestamp(iso_ts: str) -> str:
    """Extract HH:MM from an ISO timestamp string."""
    try:
        # ISO format: 2024-01-15T14:30:00.000Z or similar
        # Find the T separator
        t_idx = iso_ts.find("T")
        if t_idx >= 0:
            time_part = iso_ts[t_idx + 1:]
            return time_part[:5]  # HH:MM
        # Fallback: try splitting on space
        parts = iso_ts.split(" ")
        if len(parts) >= 2:
            return parts[1][:5]
    except Exception:
        pass
    return "??:??"


def _extract_content(content_raw: object, max_len: int) -> str:
    """Extract text content from a message content field."""
    if isinstance(content_raw, str):
        return content_raw[:max_len]

    if isinstance(content_raw, list):
        # Find the first useful block
        for block in content_raw:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type", "")
            if block_type == "text":
                text = block.get("text", "")
                return text[:max_len]
            elif block_type == "toolCall":
                name = block.get("name", "") or block.get("tool", "") or "unknown"
                return f"[tool: {name}]"
            elif block_type == "toolResult":
                # Show first max_len chars of the result content
                result = block.get("content", "")
                if isinstance(result, str):
                    return result[:max_len]
                elif isinstance(result, list):
                    # Nested content blocks
                    for sub in result:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            return sub.get("text", "")[:max_len]
                return str(result)[:max_len]
        # No recognised block found
        return ""

    return str(content_raw)[:max_len]


_ROLE_MAP: dict[str, str] = {
    "user": "user",
    "assistant": "assistant",
    "toolResult": "tool",
}


def read_transcript(
    session_id: str,
    agent_id: str,
    limit: int = 20,
    max_content_len: int = 200,
) -> list[TranscriptMessage]:
    """Read last `limit` messages from a session transcript.

    File location: ~/.openclaw/agents/<agent_id>/sessions/<session_id>.jsonl
    """
    path = OPENCLAW_DIR / "agents" / agent_id / "sessions" / f"{session_id}.jsonl"

    if not path.exists():
        logger.warning("Transcript file not found: %s", path)
        return []

    messages: list[TranscriptMessage] = []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed to read transcript %s: %s", path, exc)
        return []

    for lineno, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.debug("Skipping malformed JSON at line %d of %s: %s", lineno, path, exc)
            continue

        if not isinstance(record, dict):
            logger.debug("Skipping non-dict record at line %d of %s", lineno, path)
            continue

        if record.get("type") != "message":
            continue

        msg = record.get("message")
        if not isinstance(msg, dict):
            logger.debug("Skipping record with missing/invalid 'message' at line %d", lineno)
            continue

        raw_role = msg.get("role", "")
        role = _ROLE_MAP.get(raw_role, raw_role)

        iso_ts = record.get("timestamp", "")
        timestamp = _extract_timestamp(iso_ts)

        try:
            content = _extract_content(msg.get("content", ""), max_content_len)
        except Exception as exc:
            logger.debug("Error extracting content at line %d: %s", lineno, exc)
            content = ""

        messages.append(TranscriptMessage(timestamp=timestamp, role=role, content=content))

    return messages[-limit:]


def read_task(
    session_id: str,
    agent_id: str,
    max_content_len: int = 300,
) -> TranscriptMessage | None:
    """Return the FIRST user message from the transcript (the spawn task prompt).

    Returns None if no user message found or the file doesn't exist.
    """
    path = OPENCLAW_DIR / "agents" / agent_id / "sessions" / f"{session_id}.jsonl"

    if not path.exists():
        logger.warning("Transcript file not found: %s", path)
        return None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed to read transcript %s: %s", path, exc)
        return None

    for lineno, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.debug("Skipping malformed JSON at line %d of %s: %s", lineno, path, exc)
            continue

        if not isinstance(record, dict) or record.get("type") != "message":
            continue

        msg = record.get("message")
        if not isinstance(msg, dict):
            continue

        if msg.get("role") != "user":
            continue

        iso_ts = record.get("timestamp", "")
        timestamp = _extract_timestamp(iso_ts)
        try:
            content = _extract_content(msg.get("content", ""), max_content_len)
        except Exception as exc:
            logger.debug("Error extracting content at line %d: %s", lineno, exc)
            content = ""

        return TranscriptMessage(
            timestamp=timestamp,
            role=_ROLE_MAP.get("user", "user"),
            content=content,
        )

    return None


def read_report(
    session_id: str,
    agent_id: str,
    max_content_len: int = 500,
) -> TranscriptMessage | None:
    """Return the LAST assistant message from the transcript (the final report).

    Returns None if no assistant message found or the file doesn't exist.
    """
    path = OPENCLAW_DIR / "agents" / agent_id / "sessions" / f"{session_id}.jsonl"

    if not path.exists():
        logger.warning("Transcript file not found: %s", path)
        return None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed to read transcript %s: %s", path, exc)
        return None

    last_assistant: TranscriptMessage | None = None

    for lineno, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.debug("Skipping malformed JSON at line %d of %s: %s", lineno, path, exc)
            continue

        if not isinstance(record, dict) or record.get("type") != "message":
            continue

        msg = record.get("message")
        if not isinstance(msg, dict):
            continue

        if msg.get("role") != "assistant":
            continue

        iso_ts = record.get("timestamp", "")
        timestamp = _extract_timestamp(iso_ts)
        try:
            content = _extract_content(msg.get("content", ""), max_content_len)
        except Exception as exc:
            logger.debug("Error extracting content at line %d: %s", lineno, exc)
            content = ""

        last_assistant = TranscriptMessage(
            timestamp=timestamp,
            role=_ROLE_MAP.get("assistant", "assistant"),
            content=content,
        )

    return last_assistant


def read_transcript_incremental(
    session_id: str,
    agent_id: str,
    offset: int = 0,
    max_content_len: int = 200,
) -> tuple[list[TranscriptMessage], int]:
    """Read messages starting from byte `offset` in the transcript file.

    Returns (new_messages, new_byte_offset).
    - If file not found: returns ([], 0)
    - If file hasn't changed (size <= offset): returns ([], offset)
    - new_byte_offset is the file size after reading the new data.
    """
    path = OPENCLAW_DIR / "agents" / agent_id / "sessions" / f"{session_id}.jsonl"

    if not path.exists():
        return ([], 0)

    file_size = path.stat().st_size
    if file_size <= offset:
        return ([], offset)

    messages: list[TranscriptMessage] = []

    with open(path, "rb") as f:
        f.seek(offset)
        raw = f.read()

    new_offset = offset + len(raw)
    text = raw.decode("utf-8", errors="replace")

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            # Partial line at offset boundary — skip gracefully
            continue

        if not isinstance(record, dict) or record.get("type") != "message":
            continue

        msg = record.get("message")
        if not isinstance(msg, dict):
            continue

        raw_role = msg.get("role", "")
        role = _ROLE_MAP.get(raw_role, raw_role)
        iso_ts = record.get("timestamp", "")
        timestamp = _extract_timestamp(iso_ts)
        try:
            content = _extract_content(msg.get("content", ""), max_content_len)
        except Exception:
            content = ""

        messages.append(TranscriptMessage(timestamp=timestamp, role=role, content=content))

    return (messages, new_offset)


def get_last_activity(
    session_id: str,
    agent_id: str,
    max_len: int = 40,
) -> str | None:
    """Return truncated content of the LAST message (any role) in the transcript.

    For efficiency, reads only the last 4096 bytes of the file.
    Returns None if the file is not found or no messages are present.
    """
    path = OPENCLAW_DIR / "agents" / agent_id / "sessions" / f"{session_id}.jsonl"

    if not path.exists():
        return None

    file_size = path.stat().st_size
    read_size = min(file_size, 4096)

    with open(path, "rb") as f:
        f.seek(max(0, file_size - read_size))
        raw = f.read()

    text = raw.decode("utf-8", errors="replace")
    last_msg: str | None = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(record, dict) or record.get("type") != "message":
            continue

        msg = record.get("message", {})
        if not isinstance(msg, dict):
            continue

        try:
            content = _extract_content(msg.get("content", ""), max_len)
        except Exception:
            content = ""

        if content:
            last_msg = content

    return last_msg
