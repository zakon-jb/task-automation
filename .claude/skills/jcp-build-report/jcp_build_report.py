#!/usr/bin/env python3
"""Report JCP issues *completed* in recent TeamCity builds of several services.

For each service (Quota, Auth) it pulls successful image builds from the last N
days (default 7), reads each build's related issues via the TeamCity REST API,
and keeps only JCP-* issues that were COMPLETED in that build. An issue counts
as completed in a build when BOTH:
  1. it is resolved in YouTrack (its State is a resolved-type state), AND
  2. the build contains the issue's LAST linked commit (the newest VCS change
     referencing the issue, by date, across all builds).
This attributes each issue to the single build that shipped its final commit,
and drops issues that are not yet resolved. Each kept issue is enriched with its
subject and assignee from YouTrack, and mapped to the prod deploy that carried
it (by walking the deploy's build chain down to the image it shipped).

Output: one deployments table per service, then a combined issues table whose
"Deployment" column shows the deployed version + time per applicable service.

Auth:
  - TeamCity access token: --token or the TC_TOKEN env var.
  - YouTrack token: --yt-token or the YT_TOKEN env var. REQUIRED — the
    completion logic (resolved state + last commit) depends on it.
No third-party dependencies (uses urllib).
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_SERVER = "https://jetbrains-ai.internal.teamcity.cloud"
DEFAULT_YT_SERVER = "https://youtrack.jetbrains.com"

# Services to report on. Each has an image ("build & push") config and the prod
# deployment config the build chain leads to on release.
SERVICES = [
    {
        "name": "Quota",
        "image_config": "Deployments_GrazieAppQuotaJibBuild",
        "prod_config": "Deployments_App_Quota_Prod_ServiceEKSDeployment_EuWest1",
    },
    {
        "name": "Auth",
        "image_config": "Deployments_GrazieAuthServiceJibBuild",
        "prod_config": "Deployments_App_Auth_Prod_SpaceToECRPush_EuWest1",
    },
]
JCP_RE = re.compile(r"JCP-\d+")
# TeamCity date format, e.g. 20260720T154939+0000
TC_DATE_FMT = "%Y%m%dT%H%M%S%z"
# Display timezone: Central European Time (CET in winter, CEST in summer).
DISPLAY_TZ = ZoneInfo("Europe/Berlin")


def api_get(server, token, path, query=None, fatal=True):
    url = server.rstrip("/") + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        msg = f"HTTP {e.code} for {url}\n{body[:800]}"
        if fatal:
            sys.exit(f"ERROR: {msg}")
        print(f"WARNING: {msg}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        msg = (f"could not reach {url}: {e.reason}\n"
               "(internal/YouTrack hosts usually require VPN)")
        if fatal:
            sys.exit(f"ERROR: {msg}")
        print(f"WARNING: {msg}", file=sys.stderr)
        return None


def fetch_yt_details(yt_server, yt_token, issue_ids):
    """Return {id -> {summary, assignee, state, resolved, latest_version}}.

    latest_version is the SHA of the newest (max date) VCS change referencing the
    issue across all builds. Best-effort: ids that fail to fetch are omitted.
    """
    details = {}
    if not (yt_token and issue_ids):
        return details
    for iid in issue_ids:
        data = api_get(
            yt_server, yt_token, f"/api/issues/{iid}",
            {"fields": "idReadable,summary,resolved,"
                       "customFields(name,value(fullName,name,login))"},
            fatal=False,
        )
        if not data:
            continue
        assignee = "Unassigned"
        state = None
        for cf in data.get("customFields", []):
            name = cf.get("name")
            val = cf.get("value")
            if name == "Assignee" and val:
                assignee = val.get("fullName") or val.get("login") or "Unassigned"
            elif name == "State" and val:
                state = val.get("name")

        # Newest VCS change referencing the issue (across all builds), by date.
        vcs = api_get(
            yt_server, yt_token, f"/api/issues/{iid}/vcsChanges",
            {"fields": "version,date", "$top": "500"},
            fatal=False,
        ) or []
        latest = max(vcs, key=lambda c: c.get("date") or 0, default=None)

        details[iid] = {
            "summary": data.get("summary") or "",
            "assignee": assignee,
            "state": state,
            "resolved": bool(data.get("resolved")),
            "resolved_ms": data.get("resolved"),  # epoch millis, or None
            "latest_version": (latest or {}).get("version"),
        }
    return details


def fmt_dt(tc_date):
    """Format a TeamCity timestamp in the display timezone (CET/CEST)."""
    try:
        dt = datetime.strptime(tc_date, TC_DATE_FMT).astimezone(DISPLAY_TZ)
        return dt.strftime("%Y-%m-%d %H:%M %Z")
    except (ValueError, TypeError):
        return tc_date or "?"


def fmt_epoch_ms(ms):
    """Format a YouTrack epoch-millis timestamp in CET/CEST, or '—' if absent."""
    if not ms:
        return "—"
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(DISPLAY_TZ)
    return dt.strftime("%Y-%m-%d %H:%M %Z")


def parse_tc(dt):
    try:
        return datetime.strptime(dt, TC_DATE_FMT)
    except (ValueError, TypeError):
        return None


def resolve_image_build(server, token, deploy_id, image_config, cache):
    """Walk snapshot-dependencies DOWN from a deploy build until the image build
    (a build in `image_config`) is reached. Returns {id, number, startDate} or
    None.

    `cache` maps build id -> node dict (buildTypeId, number, startDate, deps) to
    avoid refetching shared sub-chains across deploys.
    """
    seen = set()
    stack = [str(deploy_id)]
    while stack:
        bid = stack.pop()
        if bid in seen or len(seen) > 500:
            continue
        seen.add(bid)
        if bid not in cache:
            d = api_get(
                server, token, f"/app/rest/builds/id:{bid}",
                {"fields": "id,number,buildTypeId,startDate,"
                           "snapshot-dependencies(build(id))"},
                fatal=False,
            ) or {}
            cache[bid] = {
                "buildTypeId": d.get("buildTypeId"),
                "number": d.get("number"),
                "startDate": d.get("startDate"),
                "deps": [str(b["id"])
                         for b in d.get("snapshot-dependencies", {}).get("build", [])],
            }
        node = cache[bid]
        if node["buildTypeId"] == image_config:
            return {"id": bid, "number": node["number"],
                    "startDate": node["startDate"]}
        stack.extend(node["deps"])
    return None


def resolve_prod_deploys(server, token, prod_config, image_config, since_str):
    """Return prod deploys (since `since_str`), each with the image build it
    shipped, sorted oldest-first.

    A deploy of version V delivers EVERY image build newer than the previously
    deployed version, up to and including V. So callers map a build to the
    earliest deploy whose shipped image is >= that build (by time).

    Returns list of {"number", "startDate", "image": {id, number, startDate}}.
    """
    deploys = api_get(
        server, token, "/app/rest/builds",
        {
            "locator": (f"buildType:{prod_config},sinceDate:{since_str},"
                        "status:SUCCESS,state:finished,count:1000"),
            "fields": "build(id,number,startDate)",
        },
    ).get("build", [])
    cache = {}
    out = []
    for dep in deploys:
        image = resolve_image_build(server, token, dep["id"], image_config, cache)
        if image:
            out.append({
                "number": dep.get("number"),
                "startDate": dep.get("startDate"),
                "image": image,
            })
    out.sort(key=lambda d: parse_tc(d["startDate"]) or datetime.min)
    return out


def deploy_for_build(build, deploys):
    """The earliest prod deploy whose shipped image is at least as new as `build`
    (that deploy is the release that first carried this build to prod). None if
    no deploy has caught up to this build yet."""
    b_dt = parse_tc(build.get("started"))
    best = None
    for d in deploys:
        img_dt = parse_tc(d["image"]["startDate"])
        if b_dt and img_dt and img_dt >= b_dt:
            if best is None or parse_tc(d["startDate"]) < parse_tc(best["startDate"]):
                best = d
    return best


def collect_service(args, svc, since_str, yt):
    """Build the report for one service. Returns dict with name, scanned count,
    dropped count, and `report` (builds with completed JCP issues). `yt` is a
    shared YouTrack-details cache to avoid refetching ids across services.

    Each kept issue is annotated with `service`, `deploy_version` (the prod
    version that shipped it), `deploy_date` (formatted) and `deploy_pending`.
    """
    image_config = svc["image_config"]
    prod_config = svc["prod_config"]

    builds = api_get(
        args.server, args.token, "/app/rest/builds",
        {
            # status:SUCCESS + state:finished => only successful, completed builds.
            "locator": (f"buildType:{image_config},sinceDate:{since_str},"
                        "status:SUCCESS,state:finished,count:1000"),
            "fields": "count,build(id,number,status,startDate,webUrl)",
        },
    ).get("build", [])

    report = []
    for b in builds:
        ri = api_get(
            args.server, args.token,
            f"/app/rest/builds/id:{b['id']}/relatedIssues",
            {"fields": "issueUsage(issue(id,url),changes(change(version)))"},
        )
        jcp = {}
        for usage in ri.get("issueUsage", []):
            issue = usage.get("issue", {})
            iid = issue.get("id", "")
            if not JCP_RE.fullmatch(iid or ""):
                continue
            versions = [c.get("version")
                        for c in usage.get("changes", {}).get("change", [])
                        if c.get("version")]
            jcp[iid] = {"url": issue.get("url", ""), "versions": versions}
        if jcp:
            report.append({
                "number": b.get("number"),
                "id": b.get("id"),
                "status": b.get("status"),
                "started": b.get("startDate"),
                "started_fmt": fmt_dt(b.get("startDate")),
                "webUrl": b.get("webUrl"),
                "jcp_issues": [
                    {"id": k, "url": v["url"], "versions": v["versions"]}
                    for k, v in sorted(jcp.items(),
                                       key=lambda kv: int(kv[0].split("-")[1]))
                ],
            })

    # Enrich from YouTrack (shared cache), then keep only COMPLETED issues.
    need = sorted({i["id"] for b in report for i in b["jcp_issues"]
                   if i["id"] not in yt},
                  key=lambda x: int(x.split("-")[1]))
    yt.update(fetch_yt_details(args.yt_server, args.yt_token, need))
    dropped = 0
    for b in report:
        kept = []
        for i in b["jcp_issues"]:
            d = yt.get(i["id"])
            if not d:
                dropped += 1  # cannot verify completion -> drop
                continue
            i["summary"] = d["summary"]
            i["assignee"] = d["assignee"]
            i["state"] = d["state"]
            i["resolved"] = d["resolved"]
            i["resolved_ms"] = d["resolved_ms"]
            i["resolved_date"] = fmt_epoch_ms(d["resolved_ms"])
            latest = d["latest_version"]
            i["is_last_revision"] = bool(latest and latest in i["versions"])
            if i["resolved"] and i["is_last_revision"]:
                kept.append(i)
            else:
                dropped += 1
        b["jcp_issues"] = kept
    report = [b for b in report if b["jcp_issues"]]

    # Map each build to the prod deploy that carried it, then annotate issues.
    deploys = resolve_prod_deploys(
        args.server, args.token, prod_config, image_config, since_str)
    for b in report:
        dep = deploy_for_build(b, deploys)
        b["prod_deploy"] = dep
        b["prod_deployed_fmt"] = fmt_dt(dep["startDate"]) if dep else None
        for i in b["jcp_issues"]:
            i["service"] = svc["name"]
            i["deploy_version"] = dep["image"]["number"] if dep else None
            i["deploy_date"] = b["prod_deployed_fmt"] if dep else None
            i["deploy_started"] = dep["startDate"] if dep else None  # raw TC date
            i["deploy_pending"] = dep is None

    return {
        "name": svc["name"],
        "image_config": image_config,
        "prod_config": prod_config,
        "scanned": len(builds),
        "dropped": dropped,
        "report": report,
    }


def print_deploy_table(svc_result):
    print(f"## {svc_result['name']} deployments\n")
    report = svc_result["report"]
    if not report:
        print("_No successful builds completed a JCP issue in this window._\n")
        return
    print("| Build (image) | Image built | Deployed to prod | JCP issues |")
    print("|---------------|-------------|------------------|------------|")
    for b in report:
        build = b["number"] + ("" if b["status"] == "SUCCESS"
                               else f" ({b['status']})")
        if b["prod_deploy"]:
            pd = b["prod_deploy"]
            shipped = pd["image"]["number"]
            via = "" if shipped == b["number"] else f" → {shipped}"
            prod = f"{b['prod_deployed_fmt']} (#{pd['number']}{via})"
        else:
            prod = "not yet deployed (pending)"
        issues = ", ".join(f"[{i['id']}]({i['url']})" for i in b["jcp_issues"])
        print(f"| {build} | {b['started_fmt']} | {prod} | {issues} |")
    print()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--token", default=os.environ.get("TC_TOKEN"),
                   help="TeamCity access token (default: $TC_TOKEN)")
    p.add_argument("--yt-token", default=os.environ.get("YT_TOKEN"),
                   help="YouTrack token for subjects/assignees (default: $YT_TOKEN)")
    p.add_argument("--yt-server", default=DEFAULT_YT_SERVER)
    p.add_argument("--server", default=DEFAULT_SERVER)
    p.add_argument("--days", type=int, default=7,
                   help="how many days back to include (default: 7)")
    p.add_argument("--json", action="store_true",
                   help="emit machine-readable JSON instead of Markdown")
    args = p.parse_args()

    if not args.token:
        sys.exit("ERROR: no token. Pass --token or set TC_TOKEN.")
    if not args.yt_token:
        sys.exit("ERROR: no YouTrack token. The completion logic (resolved state "
                 "+ last commit) requires it. Pass --yt-token or set YT_TOKEN.")

    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    since_str = since.strftime(TC_DATE_FMT)

    yt = {}
    results = [collect_service(args, svc, since_str, yt) for svc in SERVICES]

    if args.json:
        print(json.dumps({
            "days": args.days,
            "since": since_str,
            "services": results,
        }, indent=2))
        return

    print(f"# JCP issues completed & deployed — last {args.days} days")
    parts = [f"{r['name']}: {len(r['report'])} build(s), {r['dropped']} dropped"
             for r in results]
    print(f"_Since {fmt_dt(since_str)}. {'; '.join(parts)}._\n")

    # One deployments table per service.
    for r in results:
        print_deploy_table(r)

    # Combined issues table. An issue is attributed to one build per service;
    # aggregate per id across services for the Deployment column.
    all_issues = {}  # id -> issue (first seen)
    deployments = {}  # id -> list of "Service version (date)" strings
    deploy_sort = {}  # id -> datetime to sort by (latest deploy across services)
    for r in results:
        for b in r["report"]:
            for i in b["jcp_issues"]:
                all_issues.setdefault(i["id"], i)
                if i["deploy_pending"]:
                    cell = f"{i['service']} (pending)"
                    dt = datetime.max.replace(tzinfo=timezone.utc)  # pending first
                else:
                    cell = f"{i['service']} {i['deploy_version']} ({i['deploy_date']})"
                    dt = parse_tc(i["deploy_started"]) or datetime.min.replace(
                        tzinfo=timezone.utc)
                deployments.setdefault(i["id"], []).append(cell)
                prev = deploy_sort.get(i["id"])
                if prev is None or dt > prev:
                    deploy_sort[i["id"]] = dt

    print("## JCP Issues\n")
    print("| JCP issue | Subject | Assignee | Status | Resolved | Deployment |")
    print("|-----------|---------|----------|--------|----------|------------|")
    # Sort by deployment time (latest first); ties broken by JCP number desc.
    order = sorted(all_issues,
                   key=lambda x: (deploy_sort.get(x, datetime.min.replace(
                       tzinfo=timezone.utc)), int(x.split("-")[1])),
                   reverse=True)
    for iid in order:
        i = all_issues[iid]
        subject = (i.get("summary") or "_(unavailable)_").replace("|", "\\|")
        assignee = i.get("assignee") or "—"
        state = i.get("state") or "—"
        resolved = i.get("resolved_date") or "—"
        deploy = "; ".join(deployments.get(iid, [])) or "—"
        print(f"| [{iid}]({i['url']}) | {subject} | {assignee} | {state} "
              f"| {resolved} | {deploy} |")
    print()


if __name__ == "__main__":
    main()
