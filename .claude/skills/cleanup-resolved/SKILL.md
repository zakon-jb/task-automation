---
name: cleanup-resolved
description: Move resolved tasks under Archived section.
---

# Cleaning up resolved tasks

This skill moves resolved tasks from the Backlog to Archive section in all projects.

## What counts as a resolved task

- All resolved tasks under 'Backlog' section in any project. Projects are represented as sub-folders of zakon folder

## Instructions

1. Go through all project iteratively.
2. Identify resolved tasks in Backlog.
3. Move these tasks from Backlog to Archive section.
4. Display resolved tasks in output.

## Output format

Return a clean, structured list:

- Keep original order and contents
- Group by project

