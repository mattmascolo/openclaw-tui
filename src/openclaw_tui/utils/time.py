"""Relative time formatting for session timestamps."""


def relative_time(updated_at_ms: int, now_ms: int) -> str:
    """Format relative time. <= 30s = 'active', else '45s/14m/3h/2d ago'."""
    if now_ms < updated_at_ms:
        return "active"

    delta_ms = now_ms - updated_at_ms
    delta_seconds = delta_ms / 1000

    if delta_seconds <= 30:
        return "active"

    if delta_seconds < 60:
        return f"{int(delta_seconds)}s ago"

    if delta_seconds < 3600:
        return f"{int(delta_seconds // 60)}m ago"

    if delta_seconds < 86400:
        return f"{int(delta_seconds // 3600)}h ago"

    return f"{int(delta_seconds // 86400)}d ago"
