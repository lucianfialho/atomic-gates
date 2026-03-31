#!/bin/bash
# Quality gate: verify build passes before marking task complete
# Exit 0 = allow, Exit 2 = block with reason

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load-config.sh"

# Read hook input from stdin
INPUT=$(cat)

# Check if build is required by config
if [ "$(pipeline_require_build)" != "true" ]; then
  exit 0
fi

if [ -f "package.json" ]; then
  HAS_BUILD=$(jq -r '.scripts.build // empty' package.json 2>/dev/null)
  if [ -n "$HAS_BUILD" ]; then
    OUTPUT=$(npm run build 2>&1)
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
      echo "Build is broken. Fix build errors before completing." >&2
      echo "$OUTPUT" >&2
      exit 2
    fi
    exit 0
  fi
fi

exit 0
