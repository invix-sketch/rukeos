#!/bin/sh
# 0.4.4 desktop features (runs once). Env: RUKE_USER, RUKE_HOME, RUKE_SRC.
# Boot splash, clipboard history, dunst, USB automount, and shortcut defaults
# for existing sticks. Safe to re-run; all steps are idempotent.
set -e
H="${RUKE_HOME:-}"
U="${RUKE_USER:-}"

# ---- boot splash + quieter console ----
chmod +x /usr/local/bin/ruke-splash /etc/init.d/rukeos-splash 2>/dev/null || true
if command -v rc-update >/dev/null; then
  rc-update add rukeos-splash sysinit 2>/dev/null || true
  rc-update add rukeos-splash boot 2>/dev/null || true
fi

# Send OpenRC start messages to tty2 so tty1 can show the logo.
if [ -f /etc/inittab ]; then
  if ! grep -q 'openrc sysinit >/dev/tty2' /etc/inittab; then
    cp -a /etc/inittab /etc/inittab.rukeos-0008.bak 2>/dev/null || true
    sed -i -E \
      -e 's|^(::sysinit:)/sbin/openrc sysinit$|\1/bin/sh -c "exec /sbin/openrc sysinit >/dev/tty2 2>\&1"|' \
      -e 's|^(::wait:)/sbin/openrc boot$|\1/bin/sh -c "exec /sbin/openrc boot >/dev/tty2 2>\&1"|' \
      -e 's|^(::wait:)/sbin/openrc default$|\1/bin/sh -c "exec /sbin/openrc default >/dev/tty2 2>\&1"|' \
      /etc/inittab
  fi
fi

if [ -f /etc/rc.conf ]; then
  grep -q '^rc_interactive=' /etc/rc.conf || printf '\n# rukeOS quiet boot\nrc_interactive="NO"\n' >> /etc/rc.conf
  grep -q '^rc_verbose=' /etc/rc.conf || printf 'rc_verbose="NO"\n' >> /etc/rc.conf
fi

# If the live boot partition is writable, add splash/quiet to GRUB (skips debug entry).
patch_grub() {
  cfg=$1
  [ -f "$cfg" ] && [ -w "$cfg" ] || return 0
  grep -q ' menuentry ' "$cfg" || grep -q 'menuentry ' "$cfg" || return 0
  if grep -E 'linux .*(^| )splash( |$)' "$cfg" >/dev/null 2>&1; then
    return 0
  fi
  cp -a "$cfg" "$cfg.rukeos-0008.bak" 2>/dev/null || true
  awk '
    /linux / && $0 !~ /console=ttyS0/ && $0 !~ /nomodeset/ {
      if ($0 !~ / quiet/) sub(/linux[ \t]+[^ ]+/, "& quiet loglevel=3")
      if ($0 !~ / splash/) sub(/[ \t]*$/, " splash")
      if ($0 !~ /console=tty2/) sub(/[ \t]*$/, " console=tty2")
      if ($0 !~ /vt.global_cursor_default=0/) sub(/[ \t]*$/, " vt.global_cursor_default=0")
    }
    { print }
  ' "$cfg" > "$cfg.ruke-new" && mv -f "$cfg.ruke-new" "$cfg"
}

for root in /media/live /media/.lower /boot; do
  if [ -f "$root/boot/grub/grub.cfg" ]; then
    mount -o remount,rw "$root" 2>/dev/null || true
    patch_grub "$root/boot/grub/grub.cfg"
  fi
done
# Also try the block device that holds the live ISO, if it is mounted elsewhere.
if [ -r /media/.persist-device ] || [ -d /media/live ]; then
  :
fi

# ---- autostart helpers (home overlay may not refresh on a same-version 0.4.4 bump) ----
ensure_autostart_line() {
  file=$1
  line=$2
  [ -f "$file" ] || return 0
  grep -Fqx "$line" "$file" && return 0
  # Insert after the session-apply line when present, otherwise before the welcome terminal.
  if grep -q 'ruke-settings --apply-session' "$file"; then
    # busybox sed: append after matching line
    tmp=$file.ruke-new
    awk -v line="$line" '
      { print }
      /ruke-settings --apply-session/ && !done { print line; done=1 }
    ' "$file" > "$tmp" && mv -f "$tmp" "$file"
  else
    printf '%s\n' "$line" >> "$file"
  fi
  chmod +x "$file" 2>/dev/null || true
}

if [ -n "$H" ] && [ -f "$H/.config/autostart.sh" ]; then
  ensure_autostart_line "$H/.config/autostart.sh" 'command -v dunst >/dev/null && dunst &'
  ensure_autostart_line "$H/.config/autostart.sh" 'command -v ruke-clipboard >/dev/null && ruke-clipboard --daemon &'
  ensure_autostart_line "$H/.config/autostart.sh" 'command -v udiskie >/dev/null && udiskie --automount --notify --no-tray &'
  ensure_autostart_line "$H/.config/autostart.sh" 'command -v ruke-notify-watch >/dev/null && ruke-notify-watch &'
  chown "$U:$U" "$H/.config/autostart.sh" 2>/dev/null || true
fi

# ---- dunst config ----
if [ -n "$H" ]; then
  mkdir -p "$H/.config/dunst"
  src=${RUKE_SRC:-}/overlay/home/.config/dunst/dunstrc
  if [ ! -f "$H/.config/dunst/dunstrc" ] && [ -f "$src" ]; then
    cp -a "$src" "$H/.config/dunst/dunstrc"
    chown -R "$U:$U" "$H/.config/dunst" 2>/dev/null || true
  fi
fi
mkdir -p /etc/skel/.config/dunst
if [ -f "${RUKE_SRC:-}/overlay/home/.config/dunst/dunstrc" ]; then
  cp -a "${RUKE_SRC}/overlay/home/.config/dunst/dunstrc" /etc/skel/.config/dunst/dunstrc
fi

# ---- USB: PCManFM desktop mounts + volume settings ----
patch_pcmanfm() {
  conf=$1
  [ -f "$conf" ] || return 0
  grep -q '^\[volume\]' "$conf" || printf '\n[volume]\nmount_on_startup=1\nmount_removable=0\nautorun=0\n' >> "$conf"
  grep -q '^\[desktop\]' "$conf" || printf '\n[desktop]\nshow_mounts=1\n' >> "$conf"
  awk '
    BEGIN { in_vol=0; in_desk=0 }
    /^\[/ { in_vol=0; in_desk=0 }
    /^\[volume\]/ { in_vol=1 }
    /^\[desktop\]/ { in_desk=1 }
    in_vol && /^mount_on_startup=/ { print "mount_on_startup=1"; next }
    in_vol && /^mount_removable=/ { print "mount_removable=0"; next }
    in_desk && /^show_mounts=/ { print "show_mounts=1"; next }
    { print }
  ' "$conf" > "$conf.ruke-new" && mv -f "$conf.ruke-new" "$conf"
}

if [ -n "$H" ]; then
  patch_pcmanfm "$H/.config/pcmanfm/default/pcmanfm.conf"
  chown "$U:$U" "$H/.config/pcmanfm/default/pcmanfm.conf" 2>/dev/null || true
fi
patch_pcmanfm /etc/skel/.config/pcmanfm/default/pcmanfm.conf 2>/dev/null || true

# ---- Super+V and any other new default shortcuts ----
if [ -n "$H" ] && command -v ruke-shortcuts >/dev/null; then
  sudo -u "$U" -H env HOME="$H" USER="$U" XDG_CONFIG_HOME="$H/.config" ruke-shortcuts --apply || true
fi

# ---- start session helpers now if X is already up ----
if [ -n "$U" ]; then
  uid=$(id -u "$U" 2>/dev/null || true)
  if [ -n "$uid" ]; then
    for name in jwm dunst; do
      pid=$(pgrep -u "$uid" -x "$name" 2>/dev/null | head -n 1) || continue
      if [ -r "/proc/$pid/environ" ]; then
        disp=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^DISPLAY=//p' | head -n 1)
        dbus=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^DBUS_SESSION_BUS_ADDRESS=//p' | head -n 1)
        xauth=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^XAUTHORITY=//p' | head -n 1)
        runtime=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^XDG_RUNTIME_DIR=//p' | head -n 1)
        [ -n "$disp" ] || continue
        run() { sudo -u "$U" -H env DISPLAY="$disp" XAUTHORITY="${xauth:-$H/.Xauthority}" DBUS_SESSION_BUS_ADDRESS="$dbus" XDG_RUNTIME_DIR="${runtime:-/tmp/runtime-$uid}" HOME="$H" "$@"; }
        pgrep -u "$uid" -x dunst >/dev/null || run dunst &
        pgrep -u "$uid" -f 'ruke-clipboard --daemon' >/dev/null || run ruke-clipboard --daemon &
        pgrep -u "$uid" -x udiskie >/dev/null || run udiskie --automount --notify --no-tray &
        pgrep -u "$uid" -f 'ruke-notify-watch' >/dev/null || run ruke-notify-watch &
        break
      fi
    done
  fi
fi

chmod +x /usr/local/bin/ruke-notify /usr/local/bin/ruke-notify-watch /usr/local/bin/ruke-clipboard \
  /etc/NetworkManager/dispatcher.d/99-rukeos-notify 2>/dev/null || true

exit 0
