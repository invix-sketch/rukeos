#!/bin/sh
# every run: if the user customized appearance in Settings, put it back after overlay files are refreshed
[ -n "$RUKE_HOME" ] || exit 0
[ -f "$RUKE_HOME/.config/rukeos/appearance.conf" ] || exit 0
command -v ruke-settings >/dev/null || exit 0
HOME=$RUKE_HOME USER=${RUKE_USER:-} XDG_CONFIG_HOME=$RUKE_HOME/.config \
  ruke-settings --apply-appearance || true
exit 0
