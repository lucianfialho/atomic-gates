#!/usr/bin/env bash
#
# dev-sync.sh — mirror this checkout into Claude Code's plugin install paths.
#
# The Claude Code runtime loads plugins from ~/.claude/plugins/cache/... and
# ~/.claude/plugins/marketplaces/..., NOT from the checkout itself. During
# development we need to push changes from the checkout to those paths so
# the runtime sees them.
#
# Usage:
#   ./scripts/dev-sync.sh          # sync everything
#   ./scripts/dev-sync.sh --dry    # preview without writing
#
# This script is idempotent. Safe to run as often as you want.

set -euo pipefail

# Resolve checkout root: parent of this script's directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Known install paths. Auto-detect the version dir so bumping plugin.json
# doesn't silently desync the runtime.
_CACHE_BASE="$HOME/.claude/plugins/cache/atomic-gates/atomic-gates"
CACHE_ROOT=""
if [[ -d "$_CACHE_BASE" ]]; then
  _VER="$(ls -1 "$_CACHE_BASE" 2>/dev/null | sort -V | tail -n1)"
  if [[ -n "$_VER" ]]; then
    CACHE_ROOT="$_CACHE_BASE/$_VER"
  fi
fi
MARKETPLACE_ROOT="$HOME/.claude/plugins/marketplaces/atomic-gates"

# Subpaths to mirror. Anything not listed here stays as-is in the destination.
SYNC_DIRS=(
  ".claude-plugin"
  "hooks"
  "lib"
  "schemas"
  "templates"
  "docs"
)

DRY=""
if [[ "${1:-}" == "--dry" ]]; then
  DRY="--dry-run --itemize-changes"
  echo "[dev-sync] DRY RUN — no files will be written"
fi

sync_tree() {
  local dest="$1"
  if [[ ! -d "$dest" ]]; then
    echo "[dev-sync] skip: $dest (destination does not exist — install the plugin first)"
    return
  fi

  echo "[dev-sync] syncing → $dest"
  for sub in "${SYNC_DIRS[@]}"; do
    local src="$REPO_ROOT/$sub/"
    local tgt="$dest/$sub/"
    if [[ ! -d "$REPO_ROOT/$sub" ]]; then
      continue
    fi
    mkdir -p "$tgt"
    # shellcheck disable=SC2086
    rsync -a --delete \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='.DS_Store' \
      $DRY \
      "$src" "$tgt"
  done
}

sync_tree "$CACHE_ROOT"
sync_tree "$MARKETPLACE_ROOT"

echo "[dev-sync] done"
