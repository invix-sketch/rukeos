#!/bin/sh
# 0.4.2 follow-up: keyboard shortcuts include + Task Manager icon in the menu.
# Runs once. Env: RUKE_USER, RUKE_HOME, RUKE_SRC.
# Safe if 0.4.2 was already applied (same VERSION, no home overlay refresh).
set -e
H="${RUKE_HOME:-}"
U="${RUKE_USER:-}"
[ -n "$H" ] || exit 0

export HOME="$H"
export USER="${U:-$USER}"
export XDG_CONFIG_HOME="$H/.config"
mkdir -p "$H/.config/rukeos"

if command -v ruke-shortcuts >/dev/null; then
  ruke-shortcuts --ensure || true
elif [ -f /usr/share/rukeos/settings/shortcuts.py ]; then
  python3 /usr/share/rukeos/settings/shortcuts.py --ensure || true
fi

# Point the menu Task Manager entry at the purple pack icon without rewriting the rest of the file
menu="$H/.config/jgmenu/menu.csv"
if [ -f "$menu" ]; then
  python3 - "$menu" << 'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
icon = "/usr/share/icons/hicolor/24x24/apps/ruke-task-manager.png"
out = []
changed = False
for line in text.splitlines(True):
    if line.startswith("Task Manager,") and "ruke-task-manager" not in line:
        # CSV is label,command,icon — command has no commas
        parts = line.rstrip("\n").split(",")
        if len(parts) >= 3:
            parts[-1] = icon
            line = ",".join(parts) + "\n"
            changed = True
    out.append(line)
if changed:
    p.write_text("".join(out), encoding="utf-8")
PY
fi

if [ -n "$U" ]; then
  chown -R "$U:$U" "$H/.config/rukeos" 2>/dev/null || true
  [ -f "$H/.jwmrc" ] && chown "$U:$U" "$H/.jwmrc" 2>/dev/null || true
  [ -f "$menu" ] && chown "$U:$U" "$menu" 2>/dev/null || true
fi

gtk-update-icon-cache -f /usr/share/icons/rukeOS 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
exit 0
