# Design: v3 — Live Streaming + Task/Report + Activity Snippets

Patch (Structural) — three features adding real-time agent visibility.

## Brief

**Jobs to be done:**
1. Matt can see what task was assigned to each agent and what it reported back
2. Matt can watch an agent work in real-time as messages appear
3. Matt can see a one-line summary of each session's last activity in the tree

**Appetite:** 1.5 hours.

---

## Feature 1: Task & Report View

When a session is selected, the log panel shows:
- **Header:** "📋 TASK" + first user message (the spawn prompt)
- **Body:** Recent messages (scrollable)
- **Footer:** "📊 REPORT" + last assistant message (the final output)

For main session contexts (not spawned), "TASK" section is omitted (no spawn prompt).

## Feature 2: Live Log Streaming

Instead of a static snapshot, the log panel tails the transcript file:
- On session select: read full transcript, display, record byte offset
- Every 2 seconds: check if file has grown, read new bytes, parse new messages, append
- When switching sessions: reset and load new session
- Uses file size check (cheap) before reading (avoids re-reading unchanged files)

## Feature 3: Last Activity Snippet  

Tree labels include a truncated snippet of the last message:
```
● webchat (opus-4-6) 132K — "Both builders spawned..."
○ Cron: Nightly (opus-4-6) 28K — "HEARTBEAT_OK"
```

Computed during session poll — cache snippets to avoid reading all transcripts every 2s.
Only refresh snippets every 10 seconds (5 poll cycles).

---

## Changes

### Modified: `src/openclaw_tui/transcript.py`

Add three functions:

```python
def read_task(session_id: str, agent_id: str, max_content_len: int = 300) -> TranscriptMessage | None:
    """Return the first user message from a transcript (the spawn task).
    Returns None if no user message found or file doesn't exist."""

def read_report(session_id: str, agent_id: str, max_content_len: int = 500) -> TranscriptMessage | None:
    """Return the last assistant message from a transcript (the final report).
    Returns None if no assistant message found or file doesn't exist."""

def read_transcript_incremental(
    session_id: str, agent_id: str, offset: int = 0, max_content_len: int = 200
) -> tuple[list[TranscriptMessage], int]:
    """Read new messages from byte offset. Returns (new_messages, new_offset).
    If offset=0, reads entire file. Uses file seek for efficiency.
    Returns ([], offset) if file unchanged or not found."""

def get_last_activity(session_id: str, agent_id: str, max_len: int = 40) -> str | None:
    """Return truncated content of the last message in a transcript.
    Reads only the last 4KB of the file for efficiency.
    Returns None if file not found or empty."""
```

### Modified: `src/openclaw_tui/widgets/log_panel.py`

```python
class LogPanel(RichLog):
    # Existing methods stay.
    # Add:
    
    def show_task_and_messages(
        self, task: TranscriptMessage | None, messages: list[TranscriptMessage], report: TranscriptMessage | None
    ) -> None:
        """Display task header, messages, and report footer.
        Task shown with 📋 header, report with 📊 header.
        If task is None (main session), skip task section."""
    
    def append_messages(self, messages: list[TranscriptMessage]) -> None:
        """Append new messages without clearing. For live streaming."""
```

### Modified: `src/openclaw_tui/widgets/agent_tree.py`

- `_session_label()` accepts optional `snippet: str | None` parameter
- When snippet is present, append ` — "{snippet}"` to label (truncated, dimmed)

### Modified: `src/openclaw_tui/app.py`

New state:
```python
self._selected_session: SessionInfo | None = None
self._tail_offset: int = 0                     # byte offset for tailing
self._snippet_cache: dict[str, str] = {}        # session_id → last activity
self._snippet_refresh_counter: int = 0           # refresh every 5 polls
```

New poll behavior:
- On each 2s poll: also tail the selected session's transcript
- Every 5th poll (10s): refresh snippet cache for all sessions
- On session select: full read + show task/report, start tailing
- Pass snippet_cache to tree.update_tree() for label enrichment

---

## ADR-7: Poll-based tailing over inotify/watchdog

- **Decision:** Poll file size every 2s, read new bytes if grown
- **Context:** No inotify/watchdog installed, adding deps for a simple tail is overkill
- **Consequences:** 2s latency (acceptable), minimal CPU (stat + conditional read)

## ADR-8: Snippet caching with 10s refresh

- **Decision:** Cache last-activity snippets, refresh every 10s not every 2s
- **Context:** Reading all transcript files every 2s would be expensive (10+ file reads)
- **Consequences:** Snippets can be up to 10s stale. Acceptable for a dashboard.

---

## Plan: Work Units

### Integration Order
1. WU-1 (transcript enhancements) — no UI deps
2. WU-2 (UI + app changes) — depends on WU-1's new functions

These CAN run in parallel because WU-2 can mock the transcript functions.

### WU-1: Transcript Enhancements

**Files owned:** `src/openclaw_tui/transcript.py`, `tests/test_transcript.py`

**DO NOT MODIFY** any other files.

**Task:** Add four new functions to transcript.py: `read_task`, `read_report`, `read_transcript_incremental`, `get_last_activity`.

**Tests required:**
- read_task returns first user message
- read_task returns None when no user messages
- read_task returns None when file missing
- read_report returns last assistant message
- read_report returns None when no assistant messages
- read_transcript_incremental reads full file when offset=0
- read_transcript_incremental reads only new content when offset > 0
- read_transcript_incremental returns empty list when file unchanged
- read_transcript_incremental returns correct new offset
- get_last_activity returns truncated last message content
- get_last_activity returns None when file missing
- get_last_activity reads only tail of file (verify with small content)

### WU-2: UI + App Enhancements

**Files owned:** `src/openclaw_tui/widgets/log_panel.py`, `src/openclaw_tui/widgets/agent_tree.py`, `src/openclaw_tui/app.py`, `tests/test_log_panel.py`, `tests/test_widgets.py`, `tests/test_app.py`

**DO NOT MODIFY** transcript.py, models.py, config.py, client.py, tree.py, or their test files.

**Task:** 
1. LogPanel: add show_task_and_messages() and append_messages()
2. AgentTreeWidget: add snippet to _session_label()
3. App: live tailing, snippet cache, enhanced selection handler
