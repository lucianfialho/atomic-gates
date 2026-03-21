#!/bin/bash
# Quality gate: verify tests pass before Claude stops
# Exit 0 = allow stop, Exit 2 = block stop with reason

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')

# Don't loop — if we already ran this check, allow stop
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Detect test command
if [ -f "package.json" ]; then
  HAS_TEST=$(jq -r '.scripts.test // empty' package.json)
  if [ -n "$HAS_TEST" ]; then
    echo "Running tests..." >&2
    if ! npm test 2>&1; then
      echo "Tests are failing. Fix them before stopping." >&2
      exit 2
    fi
  fi
fi

# Python
if [ -f "pytest.ini" ] || [ -f "pyproject.toml" ]; then
  if command -v pytest &> /dev/null; then
    echo "Running pytest..." >&2
    if ! pytest 2>&1; then
      echo "Tests are failing. Fix them before stopping." >&2
      exit 2
    fi
  fi
fi

exit 0
