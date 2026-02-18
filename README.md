# OpenClaw Agent Dashboard

A live terminal dashboard for monitoring [OpenClaw](https://github.com/openclaw/openclaw) agent sessions. See every agent, session, and model at a glance — with real-time status updates and transcript viewing.

Built with [Textual](https://textual.textualize.io/) and [httpx](https://www.python-httpx.org/).

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## What It Does

```
┌── OpenClaw Agent Dashboard ──────────────────────────────────────────────┐
│ ▼ main                        │ [21:44] user: build the log panel       │
│   ● webchat (opus-4-6) 132K   │ [21:44] assistant: On it. Spawning two  │
│   ○ Cron: Nightly (opus-4-6)  │   parallel builders...                  │
│   ○ Cron: Bedtime (opus-4-6)  │ [21:45] tool: [tool: sessions_spawn]    │
│   ○ discord:#general (opus-4… │ [21:47] assistant: Both done. Running    │
│ ▼ social                       │   integration tests now.                │
│   ○ discord:#lab (sonnet-4-5)  │ [21:48] user: how do i use it?          │
│ ▼ sonnet-worker                │ [21:49] assistant: Arrow keys to nav,   │
│   ○ forge-builder (sonnet-4-5) │   Enter to view transcript...           │
├────────────────────────────────┴─────────────────────────────────────────┤
│ Active: 1  Idle: 8  Aborted: 0  Total: 9                                │
├──────────────────────────────────────────────────────────────────────────┤
│ q Quit · r Refresh · c Copy Info · ^p Command Palette                    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Left panel** — Agent tree grouped by agent ID, with live status icons and token counts.

**Right panel** — Transcript viewer. Select any session to see its recent messages, color-coded by role.

**Bottom bar** — Summary counts across all sessions.

## Features

- **Live polling** — Refreshes every 2 seconds from the OpenClaw gateway API
- **Agent grouping** — Sessions organized by agent (`main`, `sonnet-worker`, `social`, etc.)
- **Status icons** — See at a glance what's active, idle, or aborted
- **Transcript viewer** — Select a session to read its last 20 messages directly from disk
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

When you select a session and press Enter, the dashboard reads the session's transcript file directly from disk:

```
~/.openclaw/agents/<agent_id>/sessions/<session_id>.jsonl
```

Messages are color-coded:
- **Cyan** — User messages
- **Green** — Assistant responses
- **Dim** — Tool calls and results

The viewer shows the last 20 messages. Content is truncated at 200 characters per message.

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

95 tests covering models, config, client, tree building, transcript parsing, widgets, and app integration.

## Architecture

```
openclaw_tui/
├── app.py              # Main Textual app — layout, polling, event handling
├── client.py           # Gateway HTTP client (httpx)
├── config.py           # Config loader (openclaw.json + env vars)
├── models.py           # SessionInfo, AgentNode, status enums
├── transcript.py       # JSONL transcript file reader
├── tree.py             # Session → agent tree grouping logic
└── widgets/
    ├── agent_tree.py   # Left panel — Tree widget with status icons
    ├── log_panel.py    # Right panel — RichLog transcript viewer
    └── summary_bar.py  # Bottom bar — session count summary
```

## Requirements

- Python 3.12+
- A running [OpenClaw](https://github.com/openclaw/openclaw) gateway
- `xclip` for clipboard support (optional — falls back to `/tmp` file)

## License

MIT
