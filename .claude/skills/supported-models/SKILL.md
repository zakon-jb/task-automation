---
name: supported-models
description: Show all LLM models currently supported by the JetBrains AI Platform.
---

# Supported Models

Run the script `LLM/scripts/list_llm_profiles.py`, display its output, analyse it, and print insights.

## Instructions

### Step 1 — Run the script

Run:
```
python3 /Users/konstantin.zaporozhtsev/GitRepos/zakon/LLM/scripts/list_llm_profiles.py
```

The output contains:
- A human-readable table (lines that do NOT start with `#METADATA`)
- A machine-readable line starting with `#METADATA ` followed by a JSON object

Display all lines **except** the `#METADATA` line.

Parse the `#METADATA` JSON. It contains:
- `profile_providers`: `{ model_id → provider_name }` — provider name from the profiles API
- `scraped_dates`: `{ model_id → date }` — retirement dates scraped from the provider's official deprecation page
- `yt_dates`: `{ model_id → date }` — retirement dates from YouTrack custom fields

Also parse the table rows (columns: Provider, Provider Model ID, Retirement Date, YouTrack).

### Step 2 — Fetch raw YouTrack data via MCP

Use `mcp__YouTrack__search_issues` with:
- `query`: `project: JBAIP type: {LLM Retirement} #Unresolved`
- `customFieldsToReturn`: `["Provider Model ID", "LLM Provider", "Retirement Date"]`

This returns each issue's `id`, `url`, and its three custom fields.

Build a lookup: `{ provider_model_id → { issue_id, yt_provider, yt_retirement_date } }` keyed on the "Provider Model ID" custom field value.

### Step 3 — Print Insights

#### Insight 1 — Missing YouTrack issues
List every model that has a non-empty Retirement Date in the table but an empty YouTrack column.
Format: `<provider-model-id>  →  <retirement-date>`

#### Insight 2 — YouTrack issues without a matching retirement date
List every YouTrack URL that appears in the table but none of the models it covers has a Retirement Date.
Format: `<url>  (models: <model-id>, ...)`

#### Insight 3 — YouTrack issues covering more than one model
List every YouTrack URL that appears in more than one row.
Format:
```
<url>
  - <model-id-1>
  - <model-id-2>
```

#### Insight 4 — Discrepancies between official data and YouTrack
**Important:** Print this section with a prominent `⚠ DISCREPANCIES FOUND` header if any issues are found in any sub-category. Use bold or ALL-CAPS labels on each flagged item so they stand out. If the section is clean, print `No discrepancies found.` in plain text.

For every model that has a matched YouTrack issue, check each of the following.
Report any mismatches:

**a) Provider name mismatch**
Compare `profile_providers[model_id]` (from metadata) vs the `LLM Provider` custom field in the YT issue.
Format: `<model-id>: profile says "<X>", YT says "<Y>"`

**b) Retirement date mismatch or missing official source**
The only authoritative source for retirement dates is `scraped_dates` (scraped from the provider's official deprecation page). `yt_dates` is unverified — it reflects whatever was manually entered in YouTrack and must not be treated as evidence of retirement on its own.

Check two cases for every model that has a matched YouTrack issue:

1. If `scraped_dates[model_id]` exists AND `yt_dates[model_id]` exists and they differ:
   Format: `<model-id>: provider page says <X>, YT says <Y>`

2. If `yt_dates[model_id]` exists but `scraped_dates[model_id]` does NOT exist:
   The YouTrack retirement claim has no backing on the official provider page.
   Format: `<model-id>: YT says <X>, but not found on official provider deprecation page`

**c) Orphaned YouTrack issues**
List any YT issues (from the MCP result) whose "Provider Model ID" custom field does not match any model in the profiles table.
Format: `<issue-id>  (Provider Model ID: "<value>")`

If no issues are found in any category, print: `No discrepancies found.`
