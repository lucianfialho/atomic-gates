#!/usr/bin/env bash
# load-config.sh — Load pipeline.config.json values for use in skills and hooks.
#
# Usage: source this script or call individual functions.
#
# Config lookup order:
#   1. ./pipeline.config.json (repo root)
#   2. ./.claude/pipeline.config.json
#   3. Falls back to defaults
#
# Requires: jq (prints warning and uses defaults if missing)

_PIPELINE_CONFIG_FILE=""
_PIPELINE_CONFIG_CACHE=""

_find_config() {
  if [ -n "$_PIPELINE_CONFIG_FILE" ]; then
    echo "$_PIPELINE_CONFIG_FILE"
    return
  fi

  if [ -f "pipeline.config.json" ]; then
    _PIPELINE_CONFIG_FILE="pipeline.config.json"
  elif [ -f ".claude/pipeline.config.json" ]; then
    _PIPELINE_CONFIG_FILE=".claude/pipeline.config.json"
  else
    _PIPELINE_CONFIG_FILE=""
  fi

  echo "$_PIPELINE_CONFIG_FILE"
}

_read_config() {
  local key="$1"
  local default="$2"
  local config_file

  config_file=$(_find_config)

  if [ -z "$config_file" ]; then
    echo "$default"
    return
  fi

  if ! command -v jq &>/dev/null; then
    echo "$default"
    return
  fi

  local value
  value=$(jq -r "$key // empty" "$config_file" 2>/dev/null)

  if [ -z "$value" ] || [ "$value" = "null" ]; then
    echo "$default"
  else
    echo "$value"
  fi
}

# --- Public config accessors ---

pipeline_issue_label() {
  _read_config '.issues.label' 'claude'
}

pipeline_branch_prefix() {
  _read_config '.issues.branchPrefix' 'fix'
}

pipeline_auto_assign() {
  _read_config '.issues.autoAssign' 'true'
}

pipeline_max_parallel() {
  _read_config '.batch.maxParallel' '3'
}

pipeline_require_tests() {
  _read_config '.quality.requireTests' 'true'
}

pipeline_require_build() {
  _read_config '.quality.requireBuild' 'true'
}

pipeline_require_lint() {
  _read_config '.quality.requireLint' 'true'
}

pipeline_security_check() {
  _read_config '.review.securityCheck' 'true'
}

pipeline_performance_check() {
  _read_config '.review.performanceCheck' 'true'
}

pipeline_max_file_review_size() {
  _read_config '.review.maxFileReviewSize' '500'
}

pipeline_default_specialists() {
  _read_config '.specialists.defaults | join(",")' 'code-reviewer'
}

pipeline_file_pattern_specialist() {
  # Given a file path, return the matching specialist (or empty)
  local file_path="$1"
  local config_file

  config_file=$(_find_config)

  if [ -z "$config_file" ] || ! command -v jq &>/dev/null; then
    echo ""
    return
  fi

  # Get all patterns and check against the file path
  local patterns
  patterns=$(jq -r '.specialists.filePatterns // {} | to_entries[] | "\(.key)\t\(.value)"' "$config_file" 2>/dev/null)

  while IFS=$'\t' read -r pattern specialist; do
    if [ -z "$pattern" ]; then continue; fi
    # Use bash pattern matching (convert glob to regex-like check)
    # Simple glob: ** matches anything, * matches non-slash
    local regex="${pattern//\*\*/.*}"
    regex="${regex//\*/[^/]*}"
    if echo "$file_path" | grep -qE "$regex"; then
      echo "$specialist"
      return
    fi
  done <<< "$patterns"

  echo ""
}

# --- Validation ---

pipeline_validate_config() {
  local config_file
  config_file=$(_find_config)

  if [ -z "$config_file" ]; then
    echo "No pipeline.config.json found (using defaults)"
    return 0
  fi

  if ! command -v jq &>/dev/null; then
    echo "Warning: jq not installed, cannot validate config. Using defaults."
    return 0
  fi

  # Check if valid JSON
  if ! jq empty "$config_file" 2>/dev/null; then
    echo "Error: $config_file is not valid JSON"
    return 1
  fi

  # Check for unknown top-level keys
  local valid_keys='["$schema","specialists","issues","batch","quality","review"]'
  local unknown
  unknown=$(jq -r --argjson valid "$valid_keys" 'keys - $valid | .[]' "$config_file" 2>/dev/null)

  if [ -n "$unknown" ]; then
    echo "Error: Unknown config keys: $unknown"
    return 1
  fi

  # Validate specialist names
  local valid_specialists='["code-reviewer","frontend-dev","backend-dev","qa-engineer","ux-designer"]'
  local bad_specialists
  bad_specialists=$(jq -r --argjson valid "$valid_specialists" '
    (.specialists.defaults // []) - $valid | .[]
  ' "$config_file" 2>/dev/null)

  if [ -n "$bad_specialists" ]; then
    echo "Error: Unknown specialists in defaults: $bad_specialists"
    echo "Valid specialists: code-reviewer, frontend-dev, backend-dev, qa-engineer, ux-designer"
    return 1
  fi

  # Validate maxParallel range
  local max_parallel
  max_parallel=$(jq -r '.batch.maxParallel // empty' "$config_file" 2>/dev/null)
  if [ -n "$max_parallel" ]; then
    if [ "$max_parallel" -lt 1 ] || [ "$max_parallel" -gt 10 ]; then
      echo "Error: batch.maxParallel must be between 1 and 10 (got $max_parallel)"
      return 1
    fi
  fi

  echo "Config valid: $config_file"
  return 0
}
