# OpenClaw Agent Dashboard

A live terminal dashboard for monitoring [OpenClaw](https://github.com/openclaw/openclaw) agent sessions. Watch your agents work in real-time — see what they're doing, what they were told to do, and what they reported back.

Built with [Textual](https://textual.textualize.io/) and [httpx](https://www.python-httpx.org/).

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## What It Does

```
┌── OpenClaw Agent Dashboard ──────────────────────────────────────────────┐
│ ▼ main                        │ 📋 TASK                                 │
│   ▼ ● webchat                 │ Build the log panel using Software      │
│       opus-4-6 · 132K tokens  │ Forge to spin up parallel builders...   │
│   ▼ ○ Cron: Nightly           │ ────────────────────────────────────    │
│       opus-4-6 · 28K tokens   │ [21:44] user: build the log panel      │
│   ► ○ #general                │ [21:44] assistant: On it. Spawning two  │
│   ► ○ discord DM              │   parallel builders...                  │
│ ▼ social                       │ [21:47] assistant: Both done. 124/124   │
│   ► ○ #lab                     │   tests passing.                       │
│ ▼ sonnet-worker                │ ────────────────────────────────────    │
│   ▼ ● forge-builder            │ 📊 REPORT                              │
│       sonnet-4-5 · 50K tokens │ All 124 tests pass. Files modified...   │
│       · "Running tests..."    │                                         │
├────────────────────────────────┴─────────────────────────────────────────┤
│ Active: 2  Idle: 7  Aborted: 0  Total: 9                                │
├──────────────────────────────────────────────────────────────────────────┤
│ q Quit  r Refresh  c Copy Info  e Expand All  v View Logs  ^p palette    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Left panel** — Agent tree with nested layout: session name on one line, model/tokens/activity on the next.

**Right panel** — Transcript viewer with task prompt (📋), live messages, and final report (📊). Toggleable with `v`.

**Bottom bar** — Summary counts across all sessions.

## Features

- **Live polling** — Refreshes every 2 seconds from the OpenClaw gateway API
- **Agent grouping** — Sessions organized by agent (`main`, `sonnet-worker`, `social`, etc.)
- **Status icons** — See at a glance what's active, idle, or aborted
- **Nested tree layout** — Clean two-line display: name + status on line 1, metadata on line 2
- **Smart display names** — Raw session keys cleaned up (`discord:GUILD#general` → `#general`, `webchat:g-agent-main-main` → `webchat`)
- **Live log streaming** — Transcript auto-updates every 2s while viewing a session
- **Task & Report view** — See the original task prompt (📋) and final report (📊) for any session
- **Activity snippets** — One-line preview of each session's last message in the tree
- **Toggleable log panel** — Press `v` to show/hide the right panel; tree goes full-width
- **Expand/collapse** — Press `e` to toggle all session details; click individual sessions to expand
- **Copy to clipboard** — Press `c` to copy the selected session's details
- **Zero config** — Reads your existing `~/.openclaw/openclaw.json` automatically

## Install

```bash
git clone https://github.com/mattmascolo/openclaw-tui.git
cd openclaw-tui
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Quick alias** (optional):
```bash
echo 'alias agents="source /path/to/openclaw-tui/.venv/bin/activate && python -m openclaw_tui"' >> ~/.bashrc
```

## Run

```bash
source .venv/bin/activate
python -m openclaw_tui
```

Your OpenClaw gateway must be running. The dashboard reads connection details from your existing config — no setup needed.

## Keybindings

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate sessions |
| `Enter` | View selected session's transcript |
| `v` | Toggle log panel on/off (tree goes full-width) |
| `e` | Expand/collapse all session details |
| `r` | Force refresh |
| `c` | Copy selected session info to clipboard |
| `q` | Quit |
| `Ctrl+P` | Command palette |

## Status Icons

| Icon | Meaning |
|------|---------|
| `●` | **Active** — updated within the last 30 seconds |
| `○` | **Idle** — no recent activity |
| `⚠` | **Aborted** — last run was aborted |

## Configuration

The dashboard auto-reads your OpenClaw gateway config. No separate configuration needed.

**Config file** (`~/.openclaw/openclaw.json`):
```json
{
  "gateway": {
    "port": 2020,
    "auth": {
      "token": "your-gateway-token"
    }
  }
}
```

**Environment variable overrides** (take precedence over config file):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENCLAW_GATEWAY_HOST` | Gateway hostname | `127.0.0.1` |
| `OPENCLAW_GATEWAY_PORT` | Gateway port | `2020` |
| `OPENCLAW_WEBHOOK_TOKEN` | Bearer auth token | from config file |

## Transcript Viewer

Select a session and press Enter to view its transcript. The dashboard reads `.jsonl` transcript files directly from disk:

```
~/.openclaw/agents/<agent_id>/sessions/<session_id>.jsonl
```

The viewer shows three sections:
- **📋 TASK** — The first user message (the original prompt or task)
- **Messages** — Recent conversation history, color-coded by role (cyan = user, green = assistant, dim = tool)
- **📊 REPORT** — The last assistant message (final output or report)

Messages stream in live — stay on a session and watch new messages appear every 2 seconds.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

124 tests covering models, config, client, tree building, transcript parsing, widgets, and app integration.

## Architecture

```
openclaw_tui/
├── app.py              # Main Textual app — layout, polling, event handling
├── client.py           # Gateway HTTP client (httpx)
├── config.py           # Config loader (openclaw.json + env vars)
├── models.py           # SessionInfo, AgentNode, status enums
├── transcript.py       # JSONL transcript file reader + incremental tailing
├── tree.py             # Session → agent tree grouping logic
└── widgets/
    ├── agent_tree.py   # Left panel — nested tree with clean display names
    ├── log_panel.py    # Right panel — task/report/streaming log viewer
    └── summary_bar.py  # Bottom bar — session count summary
```

## Requirements

- Python 3.12+
- A running [OpenClaw](https://github.com/openclaw/openclaw) gateway
- `xclip` for clipboard support (optional — falls back to `/tmp` file)

## License

MIT
