#!/usr/bin/env bash
# Claude Code status line.
# Reads the session JSON from stdin and prints: model | current-dir | git-branch
set -euo pipefail

input=$(cat)

model=$(printf '%s' "$input" | jq -r '.model.display_name // "Claude"')
dir=$(printf '%s' "$input" | jq -r '.workspace.current_dir // empty')
[ -z "$dir" ] && dir="$PWD"

cwd=$(basename "$dir")
branch=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null || true)

out="$model | $cwd"
[ -n "$branch" ] && out="$out | ⎇ $branch"

printf '%s' "$out"
