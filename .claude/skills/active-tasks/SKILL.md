---
name: active-tasks
description: Show all tasks tagged #active.
---

# Active Tasks Viewer

This skill finds and lists all active tasks from `/zakon/Task Management.md`.

## What counts as a task
- All tasks under the `Active` section of `/zakon/Task Management.md`

## Instructions

1. Identify all active tasks in task management.
2. Group tasks by priority.
3. For each priority, display a separate section in the same format.
4. Preserve original task order inside each priority group.

## Output format

Return the result as a structured report.

For every priority that has tasks:

1. Print the priority line: `<Priority>`
3. Print a table with these columns:
   - `#`
   - `Project`
   - `Task`
   - `Status`

## Formatting rules

1. Use the exact visual structure below for every priority section.
2. Number rows using priority prefixes:
   - Urgent → `U1, U2, U3, ...`
   - High → `H1, H2, H3, ...`
   - Medium → `M1, M2, ...`
   - Low → `L1, L2, ...`
3. Restart numbering from 1 within each priority.
4. Keep task text unchanged.
5. Extract and display project and status if present.
6. Do not merge priorities into one table.
7. Do not use dash bullets for tasks.

## Example layout

Urgent

| # | Project | Task | Status |
|---|------|---------|--------|
| U1 | JCP | Dogfooding wire - how technically can it work with our staging? | In Progress |
| U2 | LLM | Can we freeze AI licenses after migration? | In Progress |

High

| # | Project | Task | Status |
|---|------|---------|--------|
| H1 | JCP | Annual $200 or $240 ($20 x 12) | In Progress |
| H2 | LLM | Minutes e2e seats | Todo |