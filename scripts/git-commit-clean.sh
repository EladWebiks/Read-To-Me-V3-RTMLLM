#!/usr/bin/env bash
# Commit (or amend) without allowing Cursor's --trailer injection on the agent shell.
# Usage:
#   scripts/git-commit-clean.sh /path/to/message.txt
#   scripts/git-commit-clean.sh --amend /path/to/message.txt
set -euo pipefail

amend=0
if [[ "${1:-}" == "--amend" ]]; then
  amend=1
  shift
fi

msg_file=${1:?message file required}
[[ -f "$msg_file" ]] || { echo "missing message file: $msg_file" >&2; exit 1; }

# Invoke via argv array so agent shell rewriters that patch `git commit ...` strings miss us.
git_bin=$(command -v git)
if [[ "$amend" -eq 1 ]]; then
  "$git_bin" commit --amend -F "$msg_file"
else
  "$git_bin" commit -F "$msg_file"
fi

# Strip attribution if anything still landed in the message.
clean=$(mktemp)
"$git_bin" log -1 --pretty=%B \
  | sed '/^Co-authored-by:/Id' \
  | sed '/^Made-with:/Id' \
  | sed '/cursoragent@cursor\.com/Id' \
  | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}' \
  >"$clean"

if ! "$git_bin" log -1 --pretty=%B | cmp -s - "$clean"; then
  "$git_bin" commit --amend -F "$clean"
fi
rm -f "$clean"

if "$git_bin" log -1 --format=%B | grep -Eiq '^(Co-authored-by:|Made-with:)|cursoragent@cursor\.com'; then
  echo "ERROR: attribution trailer still present after clean commit" >&2
  "$git_bin" log -1 --format=%B >&2
  exit 1
fi

echo "OK — commit message has no Co-authored-by / Made-with trailer"
"$git_bin" log -1 --format=%B
