#!/usr/bin/env python3
"""Send a Discord notification to the project owner.

Usage:
    python3 tools/notify.py --from claude --kind input "Need your OK on X"
    python3 tools/notify.py --from deepseek --kind done "T002 finished"
    python3 tools/notify.py --hook          # Claude Code Notification hook (reads JSON on stdin)

Kinds: input (your input is needed), done (task finished), blocked, info.
Reads DISCORD_WEBHOOK_URL from the environment or .env. Never prints the URL.
Always exits 0 so it can't break an agent or a hook. Stdlib only (runs on any python3).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = {
    "input": ("Your input is needed", 0xF1C40F),
    "done": ("Task finished", 0x2ECC71),
    "blocked": ("Blocked", 0xE74C3C),
    "info": ("Update", 0x3498DB),
}
AGENTS = {"claude": "Claude (orchestrator)", "deepseek": "DeepSeek (implementer)"}


def webhook_url():
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    env_path = os.path.join(ROOT, ".env")
    if not url and os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DISCORD_WEBHOOK_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
    return url


def send(agent, kind, message):
    url = webhook_url()
    if not url:
        print("notify: DISCORD_WEBHOOK_URL not set; skipped", file=sys.stderr)
        return
    title, color = KINDS[kind]
    payload = {
        "username": "didyouhit agents",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": f"{title}: {AGENTS.get(agent, agent)}",
            "description": message[:3500],
            "color": color,
            "footer": {"text": "didyouhit.gg"},
        }],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "didyouhit-notify/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError as e:
        print(f"notify: Discord returned HTTP {e.code}", file=sys.stderr)
    except (urllib.error.URLError, OSError) as e:
        print(f"notify: failed ({type(e).__name__})", file=sys.stderr)


def from_hook():
    """Claude Code Notification hook: forward permission/question prompts, skip idle nags."""
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    ntype = data.get("notification_type", "")
    message = data.get("message", "")
    if ntype == "idle_prompt" or "waiting for your input" in message.lower():
        return  # agents send explicit done/input notifications instead
    send("agent", "input", f"{message or 'An agent needs your attention.'}\n(from Claude Code hook)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("message", nargs="?", default="")
    ap.add_argument("--from", dest="agent", choices=sorted(AGENTS), default="claude")
    ap.add_argument("--kind", choices=sorted(KINDS), default="info")
    ap.add_argument("--hook", action="store_true", help="read a Claude Code hook event from stdin")
    args = ap.parse_args()
    if args.hook:
        from_hook()
    elif args.message:
        send(args.agent, args.kind, args.message)
    else:
        print("notify: no message given", file=sys.stderr)


if __name__ == "__main__":
    main()
