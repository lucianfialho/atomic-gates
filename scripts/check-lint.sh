#!/bin/bash
# Async hook: run linter after file edits
# Runs in background, reports results to Claude via systemMessage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load-config.sh"

# Check if lint is required by config
if [ "$(pipeline_require_lint)" != "true" ]; then
  exit 0
fi

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Skip non-source files
case "$FILE_PATH" in
  *.ts|*.tsx|*.js|*.jsx|*.py|*.rb|*.go|*.rs)
    ;;
  *)
    exit 0
    ;;
esac

# Detect and run linter
if [ -f "package.json" ]; then
  HAS_LINT=$(jq -r '.scripts.lint // empty' package.json 2>/dev/null)
  if [ -n "$HAS_LINT" ]; then
    OUTPUT=$(npm run lint 2>&1)
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
      echo "{\"systemMessage\": \"Lint issues found after editing $FILE_PATH:\\n$OUTPUT\"}"
    fi
    exit 0
  fi
fi

exit 0
