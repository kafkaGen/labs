#!/usr/bin/env bash
# Fails if any non-merge commit in <base>..<head> is not a conventional commit.
# Keeps history readable and release-ready: tools that read commit types (changelogs, version bumps) need them.
set -euo pipefail

base="${1:?usage: verify-conventional-commits.sh <base-ref> [head-ref]}"
head="${2:-HEAD}"
pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9._-]+\))?!?: .+'

commits="$(git log --no-merges --format='%h %s' "$base..$head")"
if [[ -z "$commits" ]]; then
  exit 0
fi

status=0
while IFS= read -r line; do
  sha="${line%% *}"
  subject="${line#* }"
  if ! grep -Eq "$pattern" <<<"$subject"; then
    echo "::error::$sha is not a conventional commit: $subject"
    status=1
  fi
done <<<"$commits"

exit "$status"
