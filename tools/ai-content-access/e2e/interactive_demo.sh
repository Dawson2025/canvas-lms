#!/usr/bin/env bash
# Launch the two-phase (scripted -> interactive) Course AI Assistant demo, HEADED,
# with voice narration. Defaults to TYPED input in this terminal; pass --voice for
# hands-free mic input (ai-audio voicemode listen).
#
#   ./interactive_demo.sh            # scripted intro, then TYPE your requests here
#   ./interactive_demo.sh --voice    # scripted intro, then SPEAK your requests
#   ./interactive_demo.sh --no-script # skip the scripted intro, go straight to interactive
#   ./interactive_demo.sh --quiet     # no TTS narration (text only)
#
# Requires: Canvas up at $BASE_URL, the agent server on $AGENT_BASE (:8742),
# DISPLAY for the headed window, and ~/.config/secrets/openrouter.env for the
# LLM "demo director".
set -euo pipefail
cd "$(dirname "$0")"

export DISPLAY="${DISPLAY:-:0}"
export BASE_URL="${BASE_URL:-http://canvas.docker}"
export AGENT_BASE="${AGENT_BASE:-http://127.0.0.1:8742}"
export SPEAK="${SPEAK:-1}"
export SCRIPTED="${SCRIPTED:-1}"
export VOICE_IN="${VOICE_IN:-0}"
export SLOW_MO="${SLOW_MO:-450}"

# Load the OpenRouter key for the director (never printed).
if [[ -z "${OPENROUTER_API_KEY:-}" && -f "$HOME/.config/secrets/openrouter.env" ]]; then
  export OPENROUTER_API_KEY="$(grep '^OPENROUTER_API_KEY=' "$HOME/.config/secrets/openrouter.env" | cut -d= -f2- | tr -d '"')"
fi

for arg in "$@"; do
  case "$arg" in
    --voice)     export VOICE_IN=1 ;;
    --no-script) export SCRIPTED=0 ;;
    --quiet)     export SPEAK=0 ;;
    --close)     export CLOSE_ON_EXIT=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

echo "Course AI Assistant demo  |  BASE=$BASE_URL  AGENT=$AGENT_BASE"
echo "  scripted=$SCRIPTED  voice_in=$VOICE_IN  speak=$SPEAK  display=$DISPLAY"
exec python3 interactive_demo.py
