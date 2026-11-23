#!/bin/sh
# 0.2 -> 0.3 (runs once). Env: RUKE_USER, RUKE_HOME, RUKE_SRC.
set -e
# keep the USB stick's kernel: apk must never replace linux-lts (its modules must match the boot kernel)
kv=$(apk list -I linux-lts 2>/dev/null | sed -n 's/^linux-lts-\([^ ]*\) .*/\1/p' | head -1)
[ -n "$kv" ] && { grep -qx "linux-lts=$kv" /etc/apk/world || apk add -q --no-progress "linux-lts=$kv"; }
# icon cache so the new browser/updater icons show in the menu
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
# NetSurf stays as the "lite" browser; nothing else to migrate
exit 0
