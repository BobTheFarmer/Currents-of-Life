#!/bin/bash
# Runs Unity headlessly to compile the project and write results to compile_log.txt
# Usage (from Mac terminal): bash "/Users/.../Build4Good 2026/test.sh"
# Or from Claude Code chat:  ! bash "/workspace/Build4Good 2026/test.sh"

UNITY="/Applications/Unity/Hub/Editor/6000.3.9f1/Unity.app/Contents/MacOS/Unity"
PROJECT="$(cd "$(dirname "$0")" && pwd)"
LOG="$PROJECT/compile_log.txt"

echo "Running Unity compile check..."
"$UNITY" \
  -batchmode \
  -projectPath "$PROJECT" \
  -logFile "$LOG" \
  -quit 2>&1

# Summarise result
if grep -q "^- starting compilation" "$LOG" 2>/dev/null; then
  ERRORS=$(grep -c "error CS" "$LOG" 2>/dev/null || echo 0)
  WARNINGS=$(grep -c "warning CS" "$LOG" 2>/dev/null || echo 0)
  echo "Done. Errors: $ERRORS  Warnings: $WARNINGS"
  echo "Full log: $LOG"
else
  echo "Done (log written to $LOG)"
fi
