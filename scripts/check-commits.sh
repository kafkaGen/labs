#!/usr/bin/env bash
# Fails if any non-merge commit in <base>..<head> is not a conventional commit.
# release-please reads these messages to pick version bumps, so a bad one silently skips a release.
set -euo pipefail

base="${1:?usage: check-commits.sh <base-ref> [head-ref]}"
head="${2:-HEAD}"
pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9._-]+\))?!?: .+'

status=0
while IFS= read -r line; do
  sha="${line%% *}"
  subject="${line#* }"
  if ! grep -Eq "$pattern" <<<"$subject"; then
    echo "::error::$sha is not a conventional commit: $subject"
    status=1
  fi
done < <(git log --no-merges --format='%h %s' "$base..$head")

exit "$status"
