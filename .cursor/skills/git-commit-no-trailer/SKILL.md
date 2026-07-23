---
name: git-commit-no-trailer
description: >-
  Create git commits with zero trailers and no Cursor Co-authored-by.
  Use whenever the user asks to commit, amend, or push; never use --trailer.
---

# Git commit — no trailer / no Cursor co-author

## Required workflow

1. Stage only what the user asked (never `.env` / secrets).
2. **Never** run a shell string that starts with / contains bare `git commit` — Cursor's agent shell rewrites those to inject `--trailer "Co-authored-by: Cursor <cursoragent@cursor.com>"` even when you did not type it.
3. Always commit via the wrapper (writes message file, then calls git by argv):

```bash
printf '%s\n' 'Subject line.' '' 'Body.' > /tmp/commit-msg.txt
bash scripts/git-commit-clean.sh /tmp/commit-msg.txt
```

4. The wrapper verifies the message and amends again if any `Co-authored-by` / `Made-with` / `cursoragent@cursor.com` line appeared.
5. Only then push (if the user asked to push): `git push -u origin HEAD`

## Hard bans

- Do **not** use `git commit --trailer` ever.
- Do **not** put `git commit` / `git commit --amend` directly in a Shell tool command — use `scripts/git-commit-clean.sh`.
- Do **not** leave a Cursor-injected trailer on the commit.
- Do **not** ask the user to strip the trailer themselves.
