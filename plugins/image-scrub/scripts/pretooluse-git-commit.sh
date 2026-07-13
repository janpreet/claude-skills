#!/bin/bash
# Claude Code PreToolUse hook (matcher: Bash). If the command about to run
# is a `git commit`, scrub metadata from staged images first. Always exits 0
# so it never blocks the commit.
set -u
input=$(cat)

cwd=$(printf '%s' "$input" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if "git commit" not in d.get("tool_input", {}).get("command", ""):
    sys.exit(1)
print(d.get("cwd") or ".")
' 2>/dev/null) || exit 0

"$(dirname "$0")/scrub-staged.sh" "$cwd"
exit 0
