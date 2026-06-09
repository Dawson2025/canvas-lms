#!/usr/bin/env bash
#
# run_e2e.sh — headless CI runner for the Course AI Assistant E2E suite.
# =====================================================================
# Runs the Playwright/pytest spec against a live Canvas, prints a one-line
# PASS/FAIL summary, and appends a timestamped result line to a report log.
#
# Usage:
#   ./run_e2e.sh                 # run the whole suite headless
#   ./run_e2e.sh -k step_6       # pass-through pytest args (e.g. select a test)
#
# Env (all optional; see config.py for the full list):
#   BASE_URL        default http://canvas.docker
#   ADMIN_EMAIL     default admin@canvas.docker
#   ADMIN_PASSWORD  default canvasdev123
#   E2E_REPORT_LOG  default <e2e>/reports/e2e_report.log
#   PYTHON          python interpreter (default: python3)
#   PYTEST          pytest entrypoint (default: "$PYTHON -m pytest")
#
# Exit code mirrors pytest: 0 = all passed, non-zero = failures/errors.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# --- global playwright (python) at ~/.local/bin -----------------------------
export PATH="$HOME/.local/bin:$PATH"
PYTHON="${PYTHON:-python3}"

# --- connection defaults (overridable) --------------------------------------
export BASE_URL="${BASE_URL:-http://canvas.docker}"
export ADMIN_EMAIL="${ADMIN_EMAIL:-admin@canvas.docker}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-canvasdev123}"
export E2E_HEADLESS="${E2E_HEADLESS:-1}"

REPORT_LOG="${E2E_REPORT_LOG:-$DIR/reports/e2e_report.log}"
mkdir -p "$(dirname "$REPORT_LOG")" "$DIR/artifacts"

STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=================================================================="
echo " Course AI Assistant — E2E (headless)"
echo " BASE_URL=$BASE_URL  ADMIN_EMAIL=$ADMIN_EMAIL"
echo " report log: $REPORT_LOG"
echo "=================================================================="

# --- preflight: is Canvas reachable? ----------------------------------------
if command -v curl >/dev/null 2>&1; then
  if ! curl -ksS -o /dev/null --max-time 10 "$BASE_URL/login/canvas"; then
    echo "PREFLIGHT: WARN — $BASE_URL not reachable (tests will likely fail)."
  else
    echo "PREFLIGHT: OK — $BASE_URL reachable."
  fi
fi

# --- run pytest --------------------------------------------------------------
JUNIT="$DIR/artifacts/junit-$(date -u +%Y%m%d-%H%M%S).xml"
set -x
"$PYTHON" -m pytest -v -m e2e \
  --junitxml="$JUNIT" \
  "$@"
RC=$?
set +x

# --- summarize ---------------------------------------------------------------
if [ "$RC" -eq 0 ]; then
  RESULT="PASS"
else
  RESULT="FAIL"
fi

echo
echo "------------------------------------------------------------------"
echo " SUMMARY: $RESULT  (pytest exit=$RC)  BASE_URL=$BASE_URL"
echo "------------------------------------------------------------------"

# Append a single, grep-friendly line to the report log.
printf '%s\t%s\texit=%d\tBASE_URL=%s\tjunit=%s\n' \
  "$STAMP" "$RESULT" "$RC" "$BASE_URL" "$JUNIT" >> "$REPORT_LOG"

exit "$RC"
