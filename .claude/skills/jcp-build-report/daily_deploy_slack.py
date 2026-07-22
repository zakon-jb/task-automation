#!/usr/bin/env python3
"""Post a daily JCP deploy summary to Slack.

Runs the JCP build report in JSON mode, aggregates the completed JCP issues
across services (one entry per issue, like the report's "JCP Issues" table),
and posts a Block Kit message to Slack.

Two delivery methods, auto-selected by which env vars are set:
  * Bot token  — set SLACK_BOT_TOKEN (xoxb-…) and SLACK_CHANNEL. Posts via
    chat.postMessage. The bot must be a member of the channel (/invite it).
  * Webhook    — set SLACK_WEBHOOK (https://hooks.slack.com/services/…).
Bot token takes precedence if both are present.

Env:
  SLACK_BOT_TOKEN  bot OAuth token (xoxb-…); needs chat:write scope.
  SLACK_CHANNEL    channel id (e.g. C0123ABC) or #name; required with the token.
  SLACK_WEBHOOK    incoming webhook URL (alternative to the token).
  TC_TOKEN         (required) passed through to the report script.
  YT_TOKEN         (required) passed through to the report script.

Usage:
  python3 daily_deploy_slack.py [--days N] [--dry-run]

  --days N    how far back to scan (default 1 = since yesterday).
  --dry-run   print the Slack payload instead of posting it.

Exit codes: 0 ok (incl. "nothing to report"), 1 config/run error.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

REPORT = Path(__file__).with_name("jcp_build_report.py")


def run_report(days):
    """Run the report in JSON mode and return the parsed dict."""
    proc = subprocess.run(
        [sys.executable, str(REPORT), "--days", str(days), "--json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"report script failed (exit {proc.returncode})")
    return json.loads(proc.stdout)


def aggregate_issues(data):
    """Collapse per-build issues into one entry per JCP id, gathering the
    per-service deployment info. Returns a list sorted pending-first, then by
    deploy time newest-first (mirrors the report's JCP Issues table)."""
    issues = {}
    for service in data.get("services", []):
        for build in service.get("report", []):
            for iss in build.get("jcp_issues", []):
                entry = issues.setdefault(
                    iss["id"],
                    {
                        "id": iss["id"],
                        "url": iss["url"],
                        "summary": iss["summary"],
                        "assignee": iss["assignee"],
                        "state": iss["state"],
                        "resolved_date": iss.get("resolved_date"),
                        "deploys": {},  # service -> (version, date, pending)
                    },
                )
                entry["deploys"][iss["service"]] = (
                    iss.get("deploy_version"),
                    iss.get("deploy_date"),
                    iss.get("deploy_pending", False),
                )

    def sort_key(e):
        pending = any(p for (_, _, p) in e["deploys"].values())
        # latest deploy_started isn't in the aggregate, so sort on the shown
        # date string; pending sorts to the very top.
        latest = max((d or "" for (_, d, _) in e["deploys"].values()), default="")
        return (0 if pending else 1, latest if pending else _neg(latest))

    return sorted(issues.values(), key=sort_key)


def _neg(s):
    """Invert a string for descending sort while keeping type-stability."""
    return "".join(chr(255 - ord(c)) for c in s)


def deploy_line(deploys, order=None):
    """Format the per-service deployment string, e.g.
    'Quota 2026.3.850 (…); Auth 2026.3.1213 (…)'."""
    names = order or sorted(deploys)
    parts = []
    for svc in names:
        if svc not in deploys:
            continue
        version, date, pending = deploys[svc]
        if pending:
            parts.append(f"{svc} (pending)")
        else:
            parts.append(f"{svc} {version} ({date})")
    return "; ".join(parts)


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def short_date(deploy_date):
    """'2026-07-21 12:21 CEST' -> 'Jul 21'. Falls back to the raw string."""
    try:
        y, m, d = deploy_date.split()[0].split("-")
        return f"{MONTHS[int(m) - 1]} {int(d)}"
    except (ValueError, IndexError):
        return deploy_date


def short_time(deploy_date):
    """'2026-07-21 12:21 CEST' -> '12:21 CEST'. Falls back to the raw string."""
    parts = deploy_date.split(maxsplit=1)
    return parts[1] if len(parts) == 2 else deploy_date


SECTION_LIMIT = 2900  # Slack section text hard limit is 3000; leave headroom.


def add_group_section(blocks, header_line, issue_lines):
    """Emit one or more section blocks for a group, keeping the header on the
    first block and splitting issue lines so no block exceeds the char limit."""
    chunk, size = [header_line], len(header_line)
    for line in issue_lines:
        if size + len(line) + 1 > SECTION_LIMIT and len(chunk) > 1:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(chunk)}})
            chunk, size = [], 0
        chunk.append(line)
        size += len(line) + 1
    if chunk:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(chunk)}})


def group_by_deploy(issues, svc_order):
    """Bucket issues by their deploy batch (the set of service→version pairs).
    Any issue with a still-pending service goes to a single 'pending' bucket.
    Returns an ordered list of group dicts: pending first, then newest first."""
    groups = {}
    for e in issues:
        pending = any(p for (_, _, p) in e["deploys"].values())
        if pending:
            key = ("__pending__",)
        else:
            key = tuple(sorted((svc, ver) for svc, (ver, _, _) in e["deploys"].items()))
        g = groups.setdefault(
            key, {"pending": pending, "deploys": e["deploys"], "date": "", "issues": []}
        )
        g["issues"].append(e)
        for (_, d, _) in e["deploys"].values():
            if d and d > g["date"]:
                g["date"] = d

    def order_key(g):
        return (0, "") if g["pending"] else (1, _neg(g["date"]))

    return sorted(groups.values(), key=order_key)


def build_payload(data, issues):
    days = data.get("days")
    span = "yesterday" if days == 1 else f"last {days} days"
    svc_order = [s["name"] for s in data.get("services", [])]

    counts = " · ".join(
        f"{s['name']} {len(s.get('report', []))} builds" for s in data.get("services", [])
    )

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"🚀 JCP deploys — {span}"}}
    ]

    if not issues:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "No JCP issues completed & deployed in this window.",
                },
            }
        )
    else:
        groups = group_by_deploy(issues, svc_order)
        for idx, g in enumerate(groups):
            if idx:
                blocks.append({"type": "divider"})
            if g["pending"]:
                header_line = "⏳ *Pending deploy*"
            else:
                versions = " · ".join(
                    f"{name} {g['deploys'][name][0]} ({short_time(g['deploys'][name][1])})"
                    for name in svc_order
                    if name in g["deploys"]
                )
                header_line = f"📦  *Deployed {short_date(g['date'])}* · {versions}"

            lines = []
            for e in g["issues"]:
                summary = e["summary"].strip()
                line = f"✅ <{e['url']}|{e['id']}> — {summary} · _{e['assignee']}_"
                if g["pending"]:
                    line += f"  ({deploy_line(e['deploys'], svc_order)})"
                lines.append(line)
            add_group_section(blocks, header_line, lines)

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{len(issues)} issue(s) · {counts}"}],
        }
    )

    fallback = f"JCP deploys — {span}: {len(issues)} issue(s)"
    return {"text": fallback, "blocks": blocks}


def post_webhook(webhook, payload):
    req = urllib.request.Request(
        webhook,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode()
        if body.strip() != "ok":
            raise SystemExit(f"Slack rejected the message: {body}")


def post_api(token, channel, payload):
    """Post via chat.postMessage using a bot token."""
    body = {"channel": channel, "text": payload["text"], "blocks": payload["blocks"]}
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())
    if not result.get("ok"):
        # e.g. not_in_channel, channel_not_found, invalid_auth, missing_scope
        raise SystemExit(f"Slack API error: {result.get('error', result)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL")
    webhook = os.environ.get("SLACK_WEBHOOK")

    if not args.dry_run:
        if token and not channel:
            raise SystemExit("SLACK_CHANNEL is required when using SLACK_BOT_TOKEN")
        if not token and not webhook:
            raise SystemExit(
                "Set SLACK_BOT_TOKEN + SLACK_CHANNEL, or SLACK_WEBHOOK (or use --dry-run)"
            )

    data = run_report(args.days)
    issues = aggregate_issues(data)
    payload = build_payload(data, issues)

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if token:
        post_api(token, channel, payload)
    else:
        post_webhook(webhook, payload)
    print(f"Posted {len(issues)} issue(s) to Slack.")


if __name__ == "__main__":
    main()
