---
name: jcp-build-report
description: Report the JCP issues completed in recent successful TeamCity builds of the Grazie App Quota deployment config (last 1 week by default). An issue counts only if it is resolved in YouTrack AND the build shipped its last linked commit. For each such build shows build number, date/time, and each completed JCP issue with subject and assignee. Non-JCP issues (EMBARK, JBAIP, etc.) are ignored.
---

# JCP Build Report

Pulls recent **successful** builds from a TeamCity build configuration and
reports the **JCP** issues that were **completed** in each build, with each
issue's **subject** and **assignee**. Ignores every non-JCP issue.

An issue is "completed in a build" only when BOTH hold:
1. **Resolved** — the issue's State is a resolved-type state in YouTrack.
2. **Last revision in this build** — the newest commit linked to the issue
   (by date, across all builds) is one of the commits included in this build.

So each issue is attributed to the single build that shipped its final commit,
and issues not yet resolved are dropped.

Each reported build shows **two timestamps**:
- **Image built** — the image build's own start time.
- **Deployed to prod** — the time of the prod deploy that first carried this
  build's changes to prod. A prod deploy ships one image version and thereby
  delivers EVERY successful image build after the previously deployed version up
  to that one; so a build is attributed to the earliest prod deploy whose
  shipped image is at least as new as the build. If no deploy has caught up to
  the build yet, it shows as not yet deployed (pending).

Default image configuration: `Deployments_GrazieAppQuotaJibBuild`; default prod
configuration: `Deployments_App_Quota_Prod_ServiceEKSDeployment_EuWest1`; both on
`https://jetbrains-ai.internal.teamcity.cloud`.

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
- `--build-config <id>` — a different TeamCity buildType id.
- `--json` — machine-readable output (use this if you need to enrich in Step 2).

The script:
1. Queries **successful** builds in the window (`status:SUCCESS,state:finished`
   — failed, canceled, and running builds are ignored).
2. For each build, reads its related issues via the TeamCity REST API
   (`/app/rest/builds/id:<id>/relatedIssues`, including the commit SHAs each
   issue is linked to in that build) and keeps only ids matching `JCP-<number>`.
3. For each candidate JCP issue, fetches from YouTrack its subject, assignee,
   resolved state (`/api/issues/<id>`) and all linked commits
   (`/api/issues/<id>/vcsChanges`).
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
6. Prints a Markdown report grouped by build; only builds with at least one
   completed JCP issue are shown.

### Step 2 — Present the report

Display the script's Markdown output. It gives, per build:
- **Build number** (and status if not SUCCESS)
- **Image built** and **Deployed to prod** timestamps (UTC)
- A table of **completed JCP issues**, each with **subject** and **assignee**
  (issue id linked to YouTrack)

The summary line also reports how many JCP candidates were dropped (unresolved,
or their last commit was not in that build). If nothing qualifies, report that
no build in the window completed a JCP issue.

Use `--json` for the machine-readable form; each issue also carries `state`,
`resolved`, `is_last_revision`, and the `versions` (SHAs) it matched on.

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
  image builds on this config are sequential, so time order matches version
  order.
