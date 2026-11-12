#!/usr/bin/env bash
# Publish staged generated output through the same required gate as human work.
set -euo pipefail
: "${GH_REPO:?repository is required}"
: "${BASE_BRANCH:?base branch is required}"
: "${UPDATE_KIND:?update kind is required}"
: "${GITHUB_RUN_ID:?run identity is required}"
: "${GITHUB_RUN_ATTEMPT:?run attempt is required}"
if git diff --cached --quiet; then
  echo 'No generated changes.'
  exit 0
else
  status=$?
  if [[ "$status" -ne 1 ]]; then
    echo 'Failed to inspect staged generated output.' >&2
    exit "$status"
  fi
fi
branch="automation/${UPDATE_KIND}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
git commit -m "chore(${UPDATE_KIND}): refresh generated output"
git push origin "HEAD:refs/heads/${branch}"
pr_url=$(gh pr create --repo "$GH_REPO" --base "$BASE_BRANCH" --head "$branch" \
  --title "Refresh ${UPDATE_KIND} generated output" \
  --body 'Automated output update. Existing generation and validation rules are preserved. The required Engineering Standards gate must pass before this pull request can merge.')
# Token-created pushes/PRs do not trigger normal event workflows. Explicit
# dispatch runs the identical gate on this branch without another credential.
gh workflow run engineering.yml --repo "$GH_REPO" --ref "$branch"
gh pr merge "$pr_url" --repo "$GH_REPO" --auto --squash
