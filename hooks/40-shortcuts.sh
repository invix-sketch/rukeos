#!/bin/sh
# every run: make sure JWM includes the per-user keys file (do not overwrite custom keys)
[ -n "$RUKE_HOME" ] || exit 0
export HOME="$RUKE_HOME"
export USER="${RUKE_USER:-}"
export XDG_CONFIG_HOME="$RUKE_HOME/.config"
if command -v ruke-shortcuts >/dev/null; then
  ruke-shortcuts --ensure || true
elif [ -f /usr/share/rukeos/settings/shortcuts.py ]; then
  python3 /usr/share/rukeos/settings/shortcuts.py --ensure || true
fi
exit 0
