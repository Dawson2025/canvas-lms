#!/usr/bin/env bash
#
# install_timer.sh — install/enable the Course AI Assistant E2E systemd USER timer.
# =================================================================================
# Installs the .service + .timer into ~/.config/systemd/user, reloads, enables,
# and starts the timer. No root required (systemd --user).
#
# Usage:
#   ./install_timer.sh            # install + enable + start
#   ./install_timer.sh --status   # show timer + last run
#   ./install_timer.sh --remove    # stop, disable, remove units
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_UNIT_DIR="$HOME/.config/systemd/user"
SERVICE="canvas-ai-e2e.service"
TIMER="canvas-ai-e2e.timer"

case "${1:-install}" in
  --status)
    systemctl --user status "$TIMER" --no-pager || true
    echo "--- next runs ---"
    systemctl --user list-timers "$TIMER" --no-pager || true
    echo "--- last service run ---"
    systemctl --user status "$SERVICE" --no-pager || true
    exit 0
    ;;
  --remove)
    systemctl --user stop "$TIMER" 2>/dev/null || true
    systemctl --user disable "$TIMER" 2>/dev/null || true
    rm -f "$USER_UNIT_DIR/$SERVICE" "$USER_UNIT_DIR/$TIMER"
    systemctl --user daemon-reload
    echo "Removed $SERVICE and $TIMER."
    exit 0
    ;;
  install|"")
    ;;
  *)
    echo "Unknown arg: $1 (use: install | --status | --remove)"; exit 2;;
esac

mkdir -p "$USER_UNIT_DIR"
cp "$DIR/$SERVICE" "$USER_UNIT_DIR/$SERVICE"
cp "$DIR/$TIMER"   "$USER_UNIT_DIR/$TIMER"

systemctl --user daemon-reload
systemctl --user enable --now "$TIMER"

echo "Installed and started $TIMER."
echo "Tip: 'loginctl enable-linger $USER' so the timer fires when you're logged out."
systemctl --user list-timers "$TIMER" --no-pager || true
