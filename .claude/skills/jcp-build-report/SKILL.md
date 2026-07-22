---
name: jcp-build-report
description: Report the JCP issues completed & deployed to prod for the Grazie Quota and Auth services (last 1 week by default). An issue counts only if it is resolved in YouTrack AND a build shipped its last linked commit. Produces a deployments table per service plus a combined issues table with subject, assignee, status, resolve date, and the deployed version per service. Non-JCP issues (EMBARK, JBAIP, etc.) are ignored.
---

# JCP Build Report

Reports the **JCP** issues that were **completed** in recent **successful**
image builds of two services — **Quota** and **Auth** — and when each reached
prod. Ignores every non-JCP issue.

An issue is "completed in a build" only when BOTH hold:
1. **Resolved** — the issue's State is a resolved-type state in YouTrack.
2. **Last revision in this build** — the newest commit linked to the issue
   (by date, across all builds) is one of the commits included in this build.

So each issue is attributed to the build that shipped its final commit, and
issues not yet resolved are dropped. (Quota and Auth build from the same
monorepo, so the same commit — and thus the same issue — usually appears in both
services' images; the report shows the deployed version for each.)

Each reported build shows **two timestamps**:
- **Image built** — the image build's own start time.
- **Deployed to prod** — the time of the prod deploy that first carried this
  build's changes to prod. A prod deploy ships one image version and thereby
  delivers EVERY successful image build after the previously deployed version up
  to that one; so a build is attributed to the earliest prod deploy whose
  shipped image is at least as new as the build. If no deploy has caught up to
  the build yet, it shows as not yet deployed (pending).

Services (all on `https://jetbrains-ai.internal.teamcity.cloud`), configured in
the `SERVICES` list at the top of the script:
- **Quota** — image `Deployments_GrazieAppQuotaJibBuild`, prod
  `Deployments_App_Quota_Prod_ServiceEKSDeployment_EuWest1`.
- **Auth** — image `Deployments_GrazieAuthServiceJibBuild`, prod
  `Deployments_App_Auth_Prod_SpaceToECRPush_EuWest1`.

## Requirements

- A TeamCity access token in the `TC_TOKEN` env var (Profile → Access Tokens).
  If it is missing, ask the user to set it: `! export TC_TOKEN=<token>`.
- A YouTrack token in the `YT_TOKEN` env var — **required**: the completion
  logic (resolved state + last linked commit) and the subject/assignee columns
  all come from YouTrack. If missing, the script exits with an error.
- Network access to `*.internal.teamcity.cloud` and `youtrack.jetbrains.com`
  (usually requires VPN).

## Instructions

### Step 1 — Run the script

```
python3 /Users/konstantin.zaporozhtsev/GitRepos/zakon/.claude/skills/jcp-build-report/jcp_build_report.py --days 7
```

Options:
- `--days N` — how far back to scan (default `7`, i.e. last week).
- `--json` — machine-readable output (per-service).

For each service the script:
1. Queries **successful** image builds in the window
   (`status:SUCCESS,state:finished` — failed, canceled, running are ignored).
2. For each build, reads its related issues via the TeamCity REST API
   (`/app/rest/builds/id:<id>/relatedIssues`, including the commit SHAs each
   issue is linked to in that build) and keeps only ids matching `JCP-<number>`.
3. For each candidate JCP issue, fetches from YouTrack its subject, assignee,
   resolved state (`/api/issues/<id>`) and all linked commits
   (`/api/issues/<id>/vcsChanges`). YouTrack results are cached and shared
   across services.
4. Keeps the issue only if it is **resolved** AND the **newest linked commit**
   (max date across all its `vcsChanges`) is one of the commits this build
   shipped. Everything else is dropped (counted in the summary line).
5. Determines the prod deployment date, starting FROM the deploy config: it
   lists prod-deploy builds in the window and, for each, walks its
   `snapshot-dependencies` chain DOWN until it reaches the image build it
   shipped (recording that image's version + time). Each reported build is then
   attributed to the earliest prod deploy whose shipped image is at least as new
   as the build — because that deploy delivered every build since the previously
   deployed version. (The reverse TeamCity `snapshotDependency` locator returns
   nothing for these configs, so the chain must be walked from the deploy side.)

### Step 2 — Present the report

Display the script's Markdown output. It produces **three tables**:

**`<Service>` deployments** (one per service — Quota, then Auth) — one row per
build, columns:
- **Build (image)** — the build version (status noted if not SUCCESS)
- **Image built** — the image build's start time (CET/CEST)
- **Deployed to prod** — the prod deploy time, with deploy number and, when it
  differs, the version it shipped (e.g. `#88 → 2026.3.850`); or pending
- **JCP issues** — the completed JCP issue ids for that build (linked)

**JCP Issues** — one row per JCP issue across all services (deduped, sorted by
deployment time newest-first; not-yet-deployed issues sort to the top),
columns: **JCP issue**, **Subject**, **Assignee**, **Status** (YouTrack State),
**Resolved** (date, CET/CEST), and **Deployment** — the deployed version + time
per applicable service (e.g. `Quota 2026.3.850 (…); Auth 2026.3.1213 (…)`), or
`<Service> (pending)` if not yet deployed.

All timestamps are shown in Central European Time (`Europe/Berlin`): CET in
winter, CEST in summer, with the abbreviation printed alongside each time.

The summary line reports, per service, how many builds shipped a completed JCP
issue and how many candidates were dropped (unresolved, or their last commit was
not in that build).

Use `--json` for the machine-readable form; each issue also carries `state`,
`resolved`, `is_last_revision`, the `versions` (SHAs) it matched on, and its
`service`/`deploy_version`/`deploy_date`.

## Notes

- The candidate source is TeamCity's related-issues (issue-tracker integration),
  which matches the `JCP-` references found in the build's commit messages.
- Filtering is strict: an id must match `JCP-<digits>` exactly, so `JBAIP-*`,
  `EMBARK-*`, `JBAI-*`, etc. are excluded.
- "Resolved" uses YouTrack's built-in resolved flag, so any resolved-type state
  (Fixed, Done, …) counts without hardcoding state names.
- If an issue's last commit lands in a later build (or a build outside the
  window), it is attributed to that build, not an earlier one in which it also
  appeared.
- A prod deploy ships one image version but carries every build made since the
  previously deployed version. When several image builds sit between two prod
  deploys, they all get the later deploy's date (and the report notes which
  version the deploy shipped, e.g. "prod deploy #88, shipped in 2026.3.850").
- The image-version ordering used for "at least as new" is by build start time;
  image builds on a config are sequential, so time order matches version order.
- Quota and Auth build from the same monorepo, so a fix's commit lands in both
  services' images. The same issue therefore normally appears in both
  deployments tables (at each service's own version) and gets two entries in the
  Deployment column. This reflects that the fix shipped in both service images.
- To add or change services, edit the `SERVICES` list at the top of the script
  (each entry is `name` + `image_config` + `prod_config`).
