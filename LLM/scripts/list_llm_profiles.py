#!/usr/bin/env python3
"""
Fetches LLM profiles from the JetBrains AI Platform API and prints a table:
  Provider | Provider Model ID | Retirement Date | YouTrack

All data is gathered dynamically at runtime:
  - Profiles:          https://api.jetbrains.ai/application/v5/llm/profiles/v8
  - Retirement dates:  scraped from provider deprecation pages
  - YouTrack issues:   JBAIP project, type: LLM Retirement (REST API, custom fields)

Arguments:
  --grazie-app-token  JetBrains AI Platform JWT (required)
  --yt-token   YouTrack permanent token (Profile → Account Security → Tokens)
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional, Tuple

PROFILES_URL = "https://api.jetbrains.ai/application/v5/llm/profiles/v8"
YOUTRACK_API = "https://youtrack.jetbrains.com/api/issues"

DEPRECATION_URLS = {
    "OpenAI":    "https://developers.openai.com/api/docs/deprecations",
    "Anthropic": "https://platform.claude.com/docs/en/about-claude/model-deprecations",
    "Google":    "https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def http_get(url: str, headers: Optional[dict] = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def fetch_json(url: str, headers: Optional[dict] = None) -> object:
    return json.loads(http_get(url, headers))


class _StripTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = 0
        self.buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.buf.append(data)


def html_to_text(html: str) -> str:
    p = _StripTags()
    p.feed(html)
    return "\n".join(p.buf)


def parse_date(raw: str) -> str:
    """Normalise various date formats to YYYY-MM-DD."""
    raw = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw


# ── retirement date scrapers ──────────────────────────────────────────────────

def _scrape_openai(text: str) -> dict[str, str]:
    """
    After tag-stripping, each token appears on its own line:
      2026-10-23                    ← shutdown date
      gpt-4-turbo                   ← display name
       |                            ← within-cell separator (display name → version IDs)
      gpt-4-turbo-2024-04-09        ← version ID (deprecated)
      ,                             ← version separator
      gpt-4-turbo-completions       ← another version ID (deprecated)
      gpt-4.1                       ← replacement model (no separator before it)

    The ' | ' and ', ' are separators within the deprecated-model cell, NOT
    column separators. The replacement model has no explicit separator — it
    just follows the last version ID. Replacement models are unversioned aliases
    (e.g. "gpt-4.1") that don't appear in our versioned-ID profile set, so
    capturing them is harmless. We therefore skip separator-only lines and
    record every model-ID-shaped token for the current date.
    """
    result: dict[str, str] = {}
    current_date = None
    in_replacement = False
    date_re  = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*:?\s*$")
    model_re = re.compile(r"^\s*([a-z][a-z0-9.\-]{3,})\s*$")
    sep_re   = re.compile(r"^\s*[|,]\s*$")  # standalone ' | ' or ', ' lines (within-cell separators)
    for line in text.splitlines():
        line = line.replace("‑", "-")  # non-breaking hyphen → regular
        if m := date_re.match(line):
            current_date = m.group(1)
            in_replacement = False
        elif line.strip().startswith("$"):
            in_replacement = True  # embeddings table: price cell signals that replacement model follows
        elif sep_re.match(line):
            pass  # within-cell ' | ' or ', ' — skip, but do NOT set in_replacement
        elif current_date and not in_replacement and (m := model_re.match(line)):
            result.setdefault(m.group(1), current_date)
    return result


def _scrape_anthropic(text: str) -> dict[str, str]:
    """
    Table structure: model ID alone on a line, followed by dates on subsequent lines.
    Skips "Not sooner than ..." lines. Stops at retirement-notice section headers
    (e.g. "2026-04-14: Claude Sonnet 4 ...") to avoid mis-attributing dates to
    replacement models listed there.
    """
    result: dict[str, str] = {}
    current_model: Optional[str] = None
    last_date: Optional[str] = None
    date_re      = re.compile(r"([A-Z][a-z]+ \d{1,2},\s*\d{4})")
    model_re     = re.compile(r"^\s*(claude-[a-z0-9\-]+)\s*$")
    section_re   = re.compile(r"^\d{4}-\d{2}-\d{2}:")  # e.g. "2026-04-14: ..."

    def flush() -> None:
        nonlocal last_date
        if current_model and last_date:
            result.setdefault(current_model, last_date)
        last_date = None

    for line in text.splitlines():
        if section_re.match(line):
            break  # stop before retirement-notice sections
        if m := model_re.match(line):
            flush()
            current_model = m.group(1)
        elif current_model and "not sooner than" not in line.lower():
            if m := date_re.search(line):
                last_date = parse_date(m.group(1))

    flush()
    return result


def _scrape_google(text: str) -> dict[str, str]:
    """
    Table structure: model ID alone on a line, then GA date, then retirement date.
    The first date is the GA date (skip); the second is the retirement date (capture).
    Skips "Not before ..." rows — those models have no confirmed retirement date yet.
    """
    result: dict[str, str] = {}
    current_model: Optional[str] = None
    date_count = 0
    date_re  = re.compile(r"([A-Z][a-z]+ \d{1,2},\s*\d{4})")
    model_re = re.compile(r"^\s*(gemini-[a-z0-9.\-]+)\s*$")

    for line in text.splitlines():
        if m := model_re.match(line):
            current_model = m.group(1)
            date_count = 0
        elif current_model:
            if "not before" in line.lower():
                continue
            if m := date_re.search(line):
                date_count += 1
                if date_count == 2:  # first = GA date, second = retirement date
                    result.setdefault(current_model, parse_date(m.group(1)))

    return result


SCRAPERS = {
    "OpenAI":    _scrape_openai,
    "Anthropic": _scrape_anthropic,
    "Google":    _scrape_google,
}


def fetch_retirement_dates(model_ids: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for provider, url in DEPRECATION_URLS.items():
        try:
            html = http_get(url).decode("utf-8", errors="replace")
            data = SCRAPERS[provider](html_to_text(html))
            for mid in model_ids:
                if mid in data:
                    result[mid] = data[mid]
        except Exception as exc:
            print(f"Warning: could not scrape {provider} deprecations: {exc}", file=sys.stderr)
    return result


# ── YouTrack issues ───────────────────────────────────────────────────────────

def fetch_youtrack_issues(yt_token: str) -> Tuple[dict[str, str], dict[str, str]]:
    """
    Fetch JBAIP issues of type 'LLM Retirement'.
    Matches by the 'Provider Model ID' custom field (exact).
    Returns (model_id -> issue_url, model_id -> retirement_date).
    """
    params = urllib.parse.urlencode({
        "query":  "project: JBAIP type: {LLM Retirement} #Unresolved",
        "fields": "idReadable,customFields(name,value(name))",
        "$top":   200,
    })
    headers = {
        "Authorization": f"Bearer {yt_token}",
        "Accept":        "application/json",
    }
    try:
        issues = fetch_json(f"{YOUTRACK_API}?{params}", headers)
        if not isinstance(issues, list):
            raise ValueError(f"Unexpected response: {type(issues)}")
    except Exception as exc:
        print(f"Warning: could not fetch YouTrack issues: {exc}", file=sys.stderr)
        return {}, {}

    def _cf_str(cf: dict) -> Optional[str]:
        v = cf.get("value")
        if v is None:
            return None
        return v.get("name") if isinstance(v, dict) else str(v)

    url_map:  dict[str, str] = {}
    date_map: dict[str, str] = {}
    for issue in issues:
        readable_id = issue.get("idReadable", "")
        url = f"https://youtrack.jetbrains.com/issue/{readable_id}" if readable_id else ""
        cfs = {cf["name"]: cf for cf in issue.get("customFields", []) if "name" in cf}

        model_id = _cf_str(cfs["Provider Model ID"]) if "Provider Model ID" in cfs else None
        if not model_id or not url:
            continue

        url_map.setdefault(model_id, url)

        ret_val = cfs["Retirement Date"].get("value") if "Retirement Date" in cfs else None
        if ret_val is not None:
            try:
                date_str = datetime.utcfromtimestamp(int(ret_val) / 1000).strftime("%Y-%m-%d")
                date_map.setdefault(model_id, date_str)
            except (TypeError, ValueError):
                pass

    return url_map, date_map


# ── profiles ──────────────────────────────────────────────────────────────────

def fetch_profiles(grazie_app_token: str) -> list[dict]:
    headers = {
        "Content-Type":            "application/json",
        "Grazie-Agent":            '{"name":"llm-list-scanner","version":"dev"}',
        "Grazie-Authenticate-JWT": grazie_app_token,
    }
    return fetch_json(PROFILES_URL, headers).get("profiles", [])


# ── display ───────────────────────────────────────────────────────────────────

def print_table(
    profiles:      list[dict],
    retirement:    dict[str, str],
    issues:        dict[str, str],
    scraped_dates: dict[str, str],
) -> None:
    col1, col2, col3, col4, col5 = "Provider", "Provider Model ID", "JBAI ID", "Retirement Date", "YouTrack"
    rows = []
    for p in profiles:
        mid  = p.get("providerModelID", "")
        date = retirement.get(mid, "")
        # Mark dates that have no official source (present in yt_dates only)
        if date and mid not in scraped_dates:
            date = date + " !"
        rows.append((
            p.get("provider", ""),
            mid,
            p.get("id", ""),
            date,
            issues.get(mid, ""),
        ))
    rows.sort(key=lambda r: (r[3] == "", r[3], r[0], r[1]))

    w1 = max(len(col1), max((len(r[0]) for r in rows), default=0))
    w2 = max(len(col2), max((len(r[1]) for r in rows), default=0))
    w3 = max(len(col3), max((len(r[2]) for r in rows), default=0))
    w4 = max(len(col4), max((len(r[3]) for r in rows), default=0))
    w5 = max(len(col5), max((len(r[4]) for r in rows), default=0))

    sep    = f"+{'-'*(w1+2)}+{'-'*(w2+2)}+{'-'*(w3+2)}+{'-'*(w4+2)}+{'-'*(w5+2)}+"
    header = f"| {col1:<{w1}} | {col2:<{w2}} | {col3:<{w3}} | {col4:<{w4}} | {col5:<{w5}} |"
    print(sep)
    print(header)
    print(sep)
    for provider, mid, jbai_id, ret, issue in rows:
        print(f"| {provider:<{w1}} | {mid:<{w2}} | {jbai_id:<{w3}} | {ret:<{w4}} | {issue:<{w5}} |")
    print(sep)
    print(f"\n{len(rows)} profiles total.")
    if any(" !" in r[3] for r in rows):
        print("! = retirement date has no backing on the official provider deprecation page")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="List LLM profiles from JetBrains AI Platform.")
    parser.add_argument("--grazie-app-token", required=True, help="JetBrains AI Platform JWT")
    parser.add_argument("--yt-token", default="", help="YouTrack permanent token")
    args = parser.parse_args()

    grazie_app_token = args.grazie_app_token.strip()
    yt_token  = args.yt_token.strip()

    if not grazie_app_token:
        print("Error: --grazie-app-token must not be empty", file=sys.stderr)
        sys.exit(1)
    if not yt_token:
        print("Warning: --yt-token not provided — skipping YouTrack data.", file=sys.stderr)

    try:
        profiles = fetch_profiles(grazie_app_token)
    except Exception as exc:
        print(f"Error fetching profiles: {exc}", file=sys.stderr)
        sys.exit(1)

    model_ids           = {p.get("providerModelID", "") for p in profiles if p.get("providerModelID")}
    scraped_dates       = fetch_retirement_dates(model_ids)
    yt_issues, yt_dates = fetch_youtrack_issues(yt_token) if yt_token else ({}, {})
    retirement          = {**scraped_dates}
    retirement.update(yt_dates)  # YouTrack retirement dates take precedence over scraped dates

    print_table(profiles, retirement, yt_issues, scraped_dates)

    # Machine-readable metadata for skill analysis (not intended for human reading)
    metadata = {
        "profile_providers": {
            p.get("providerModelID", ""): p.get("provider", "")
            for p in profiles if p.get("providerModelID")
        },
        "scraped_dates": scraped_dates,
        "yt_dates":      yt_dates,
    }
    print(f"#METADATA {json.dumps(metadata)}")


if __name__ == "__main__":
    main()
