#!/bin/sh
# 0.4 -> 0.4.1. Env: RUKE_USER, RUKE_HOME, RUKE_SRC.
set -e
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
exit 0
