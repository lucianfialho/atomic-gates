#!/bin/bash
# Quality gate: verify build passes before marking task complete
# Exit 0 = allow, Exit 2 = block with reason

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load-config.sh"

INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject // "unknown"')

# Check if build is required by config
if [ "$(pipeline_require_build)" != "true" ]; then
  exit 0
fi

if [ -f "package.json" ]; then
  HAS_BUILD=$(jq -r '.scripts.build // empty' package.json)
  if [ -n "$HAS_BUILD" ]; then
    echo "Verifying build for task: $TASK_SUBJECT..." >&2
    if ! npm run build 2>&1; then
      echo "Build is broken. Fix build errors before completing: $TASK_SUBJECT" >&2
      exit 2
    fi
  fi
fi

exit 0
