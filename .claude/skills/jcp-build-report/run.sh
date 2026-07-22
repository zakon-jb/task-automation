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

# Look back far enough to cover the gap since the last run. On Monday (weekday 1)
# reach back 3 days so Friday + weekend deploys are included; otherwise just
# yesterday. `date +%u`: 1=Mon … 7=Sun.
if [[ "$(date +%u)" == "1" ]]; then
  DAYS=3
else
  DAYS=1
fi

exec /usr/bin/python3 "$DIR/daily_deploy_slack.py" --days "$DAYS"
