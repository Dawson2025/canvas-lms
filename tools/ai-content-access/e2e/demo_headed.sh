#!/usr/bin/env bash
#
# demo_headed.sh — HEADED live demo of the Course AI Assistant E2E flow.
# ======================================================================
# Opens a real Chromium window on DISPLAY=:0 with slow motion so a human can
# watch the instructor log in, enable the assistant, and chat with it.
#
# Usage:
#   ./demo_headed.sh                  # full journey, headed, slow
#   ./demo_headed.sh -k journey       # just the ordered story test
#
# Env (optional):
#   DISPLAY         X display to draw on        (default :0)
#   E2E_SLOW_MO     ms between actions          (default 250)
#   BASE_URL / ADMIN_EMAIL / ADMIN_PASSWORD     (see config.py defaults)
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export PATH="$HOME/.local/bin:$PATH"
PYTHON="${PYTHON:-python3}"

# --- force a watchable, headed run ------------------------------------------
export DISPLAY="${DISPLAY:-:0}"
export E2E_HEADLESS=0
export E2E_SLOW_MO="${E2E_SLOW_MO:-250}"

# --- connection defaults (overridable) --------------------------------------
export BASE_URL="${BASE_URL:-http://canvas.docker}"
export ADMIN_EMAIL="${ADMIN_EMAIL:-admin@canvas.docker}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-canvasdev123}"

echo "=================================================================="
echo " Course AI Assistant — E2E LIVE DEMO (headed)"
echo " DISPLAY=$DISPLAY  slow_mo=${E2E_SLOW_MO}ms"
echo " BASE_URL=$BASE_URL  ADMIN_EMAIL=$ADMIN_EMAIL"
echo "=================================================================="

if [ -z "${DISPLAY:-}" ]; then
  echo "ERROR: DISPLAY is empty — a headed browser needs an X server (try DISPLAY=:0)."
  exit 2
fi

# Default to the ordered story test for a clean narrative; -s streams the
# printed answers to the terminal as the assistant replies.
if [ "$#" -eq 0 ]; then
  set -- -k test_full_course_ai_assistant_journey
fi

exec "$PYTHON" -m pytest -v -s -m e2e "$@"
