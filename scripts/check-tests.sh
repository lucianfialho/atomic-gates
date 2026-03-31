#!/bin/bash
# Quality gate: verify tests pass before Claude stops
# Exit 0 = allow stop, Exit 2 = block stop with reason

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/load-config.sh"

# Read hook input from stdin
INPUT=$(cat)

# Check if tests are required by config
if [ "$(pipeline_require_tests)" != "true" ]; then
  exit 0
fi

# Detect and run test command
if [ -f "package.json" ]; then
  HAS_TEST=$(jq -r '.scripts.test // empty' package.json 2>/dev/null)
  if [ -n "$HAS_TEST" ]; then
    # Skip if "test" is actually a build command (check-build.sh handles that)
    # This avoids lock conflicts when both hooks run next build simultaneously
    case "$HAS_TEST" in
      *"next build"*|*"npm run build"*|*"yarn build"*|*"pnpm build"*|*"turbo build"*)
        exit 0
        ;;
    esac
    # Skip placeholder test scripts that aren't real tests
    case "$HAS_TEST" in
      *"no test specified"*|*"echo"*|"exit 0"|"exit 1"|"true"|"false")
        exit 0
        ;;
    esac
    OUTPUT=$(npm test 2>&1)
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
      echo "Tests are failing. Fix them before stopping." >&2
      echo "$OUTPUT" >&2
      exit 2
    fi
    exit 0
  fi
fi

# Python
if [ -f "pytest.ini" ] || [ -f "pyproject.toml" ]; then
  if command -v pytest &> /dev/null; then
    OUTPUT=$(pytest 2>&1)
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
      echo "Tests are failing. Fix them before stopping." >&2
      echo "$OUTPUT" >&2
      exit 2
    fi
    exit 0
  fi
fi

exit 0
