#!/usr/bin/env bash
#
# run-cc-puro.sh — run Claude Code HEADLESS on issue #89 starting from the
# same base commit the pipeline started from. Captures the resulting diff.
#
# Usage:
#   ./validation/ab_experiment/h6_micro/run-cc-puro.sh [trial_id]
#
# Output: validation/ab_experiment/h6_micro/cc-puro/trial-<id>.patch
#
# Prerequisite:
#   - analytics-copilot checked out at /Users/lucianfialho/Code/analytics-copilot
#   - `claude` CLI available on PATH (headless mode)
#   - No API key needed if `claude` already authenticated
#
# Notes:
#   - Uses a git worktree so we don't touch the main checkout.
#   - Forces CLAUDE_PROJECT_DIR to the worktree so atomic-gates' own hooks
#     DO NOT interfere (there's no .gates/config.yaml there).

set -euo pipefail

TRIAL="${1:-1}"
BASE_COMMIT="019038a89029d5a6f00609b6809980268ef42710"
TARGET_REPO="/Users/lucianfialho/Code/analytics-copilot"
WORKTREE="/tmp/h6-cc-puro-trial-${TRIAL}"
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_OUT="${OUT_DIR}/cc-puro/trial-${TRIAL}.patch"
LOG_OUT="${OUT_DIR}/cc-puro/trial-${TRIAL}.log"

echo "[h6] trial=${TRIAL}"
echo "[h6] base=${BASE_COMMIT}"
echo "[h6] worktree=${WORKTREE}"
echo "[h6] output=${PATCH_OUT}"

# 1) Clean any leftover worktree from a previous trial.
if [ -d "${WORKTREE}" ]; then
  cd "${TARGET_REPO}"
  git worktree remove --force "${WORKTREE}" || rm -rf "${WORKTREE}"
fi

# 2) Create a fresh worktree at the pre-PR base commit.
cd "${TARGET_REPO}"
git worktree add --detach "${WORKTREE}" "${BASE_COMMIT}"

# 3) Build the headless prompt: issue body verbatim, explicit "no questions".
PROMPT_FILE="$(mktemp)"
{
  echo "You are resolving a GitHub issue in the analytics-copilot repo."
  echo "DO NOT ask clarifying questions. Produce working code and tests."
  echo "Finish with a short summary of what you changed."
  echo ""
  echo "--- BEGIN ISSUE ---"
  cat "${OUT_DIR}/issue-89.md"
  echo "--- END ISSUE ---"
} > "${PROMPT_FILE}"

# 4) Run claude headless in the worktree.
#    --dangerously-skip-permissions lets it edit files without prompting.
#    We explicitly UNSET CLAUDE_PLUGIN_ROOT so atomic-gates hooks don't
#    pollute the "puro" arm.
cd "${WORKTREE}"
env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PROJECT_DIR \
  claude -p "$(cat "${PROMPT_FILE}")" \
    --dangerously-skip-permissions \
    --output-format text \
    > "${LOG_OUT}" 2>&1 \
  || { echo "[h6] claude exited non-zero — see ${LOG_OUT}"; }

# 5) Capture the diff against the base commit.
cd "${WORKTREE}"
git add -A
git diff --cached > "${PATCH_OUT}"

# 6) Summary.
PATCH_LINES=$(wc -l < "${PATCH_OUT}" | tr -d ' ')
echo "[h6] done — patch=${PATCH_OUT} (${PATCH_LINES} lines)"
echo "[h6] log=${LOG_OUT}"
echo "[h6] worktree left at ${WORKTREE} for inspection (remove manually)"

rm -f "${PROMPT_FILE}"
