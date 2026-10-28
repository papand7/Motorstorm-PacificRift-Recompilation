#!/usr/bin/env bash
# Create and configure the two PRIVATE repositories, then verify them. Pushes nothing.
# Default is a dry run that prints every command; --apply runs them (only after the owner approved owner/names).
#   bash github_setup.sh <owner> [--apply]
# Run from the workspace root (motorstorm/). Needs `gh auth status` to be valid.
set -euo pipefail
OWNER="${1:?usage: github_setup.sh <owner> [--apply]}"
APPLY="${2:-}"
A="$OWNER/motorstorm-pacific-rift-native"
B="$OWNER/motorstorm-ps3recomp"
run() { echo "+ $*"; if [ "$APPLY" = "--apply" ]; then "$@"; fi; }

# 1. Create (private, standalone: never `gh repo fork`), no push.
run gh repo create "$A" --private --disable-wiki --description "MotorStorm: Pacific Rift native PC recompilation (project, docs, tools). Private."
run gh repo create "$B" --private --disable-wiki --description "ps3recomp with MotorStorm work. Private; upstream sp00nznet/ps3recomp is fetch-only."

# 2. Verify visibility from GitHub's metadata before anything else.
for R in "$A" "$B"; do
  if [ "$APPLY" = "--apply" ]; then
    v=$(gh repo view "$R" --json visibility,isFork --jq '.visibility + " fork=" + (.isFork|tostring)')
    echo "$R: $v"; [ "$v" = "PRIVATE fork=false" ] || { echo "ABORT: $R is not a private standalone repository"; exit 1; }
  else echo "+ gh repo view $R --json visibility,isFork   # must print PRIVATE, fork=false"; fi
done

# 3. Remotes. Root: origin -> A. ps3recomp: origin stays the public upstream (push DISABLED), private -> B.
run git remote add origin "https://github.com/$A.git"
run git -C ps3recomp remote add private "https://github.com/$B.git"
run git -C ps3recomp config remote.private.tagOpt --no-tags
run git -C ps3recomp config push.default nothing
run git -C ps3recomp config branch.autoSetupMerge false
[ "$(git -C ps3recomp remote get-url --push origin)" = "DISABLED" ] || { echo "ABORT: public origin push URL is not DISABLED"; exit 1; }

# 4. Repository settings (both). Branch protection on private repositories needs GitHub Pro/Team;
#    secret scanning on private repositories needs GitHub Secret Protection. Failures there are reported, not fatal.
for R in "$A" "$B"; do
  run gh repo edit "$R" --delete-branch-on-merge=false --enable-wiki=false --enable-projects=false
  run gh api -X PUT "repos/$R/actions/permissions/workflow" -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false
  run gh api -X PUT "repos/$R/vulnerability-alerts" || true
  run gh api -X PUT "repos/$R/automated-security-fixes" || true
  run gh api -X PATCH "repos/$R" --input - <<<'{"security_and_analysis":{"secret_scanning":{"status":"enabled"},"secret_scanning_push_protection":{"status":"enabled"}}}' || true
done
# Root: only GitHub-owned actions (ci.yml uses actions/checkout and actions/setup-python, SHA-pinned).
run gh api -X PUT "repos/$A/actions/permissions" -F enabled=true -f allowed_actions=selected
run gh api -X PUT "repos/$A/actions/permissions/selected-actions" -F github_owned_allowed=true -F verified_allowed=false
# ps3recomp: Actions OFF. Upstream's workflows (linux/macos/windows on push+PR, release.yml on v* tags with
# contents:write) are on every branch; keep them from running until a reviewed lightweight workflow exists.
run gh api -X PUT "repos/$B/actions/permissions" -F enabled=false

# 5. Protect main (after main has been pushed). No required status check until ci has passed once on GitHub.
PROT='{"required_status_checks":null,"enforce_admins":false,"required_pull_request_reviews":{"required_approving_review_count":0},"restrictions":null,"allow_force_pushes":false,"allow_deletions":false,"required_linear_history":false}'
echo "# after the first push of main:"
for R in "$A" "$B"; do echo "+ gh api -X PUT repos/$R/branches/main/protection --input - <<<'$PROT'"; done
echo "# after ci passed once on GitHub (root): add required_status_checks {\"strict\":false,\"contexts\":[\"checks\"]}"
