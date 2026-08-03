#!/usr/bin/env python3
"""Ubuntu desktop notification for Claude Code hooks.

Reads the hook event JSON from stdin and shows a notify-send notification.
The first CLI argument is the fallback body used when the event JSON does
not carry a message (e.g. PreToolUse / Stop).
"""
import json
import subprocess
import sys


def main() -> int:
    fallback = sys.argv[1] if len(sys.argv) > 1 else "Claude Code"

    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}

    body = str(data.get("message") or "").strip() or fallback
    body = body[-900:]

    subprocess.run(
        ["notify-send", "-a", "Claude Code", "Claude Code", body],
        check=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
