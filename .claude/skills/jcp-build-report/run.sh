#!/bin/zsh
# Wrapper for the daily JCP deploy Slack post. Loads secrets, then runs the
# script for "yesterday". Invoked by the launchd agent (or cron, or by hand).
set -euo pipefail

DIR="/Users/konstantin.zaporozhtsev/GitRepos/zakon/.claude/skills/jcp-build-report"

# launchd runs with a minimal PATH; make python3 findable.
export PATH="/usr/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

if [[ ! -f "$DIR/secrets.env" ]]; then
  echo "missing $DIR/secrets.env (copy secrets.env.example and fill it in)" >&2
  exit 1
fi
source "$DIR/secrets.env"

exec /usr/bin/python3 "$DIR/daily_deploy_slack.py" --days 1
