#!/bin/sh
# 0.4.4 -> 0.4.5 (runs once). Env: RUKE_USER, RUKE_HOME, RUKE_SRC.
# Complete dark theme (local Adwaita-dark + Tokyo Night), custom dock,
# compositor/animations setting, and App store apk-lock behavior (code in overlay).
set -e
H="${RUKE_HOME:-}"
U="${RUKE_USER:-}"

# Theme files come from the system overlay. Re-point user settings in case a
# previous gtk.css / xsettingsd still names the wrong theme.
if [ -n "$H" ]; then
  mkdir -p "$H/.config/gtk-3.0" "$H/.config/gtk-2.0" "$H/.config/xsettingsd" "$H/.config/picom" "$H/.config/rukeos"
  if [ -f /etc/gtk-3.0/settings.ini ]; then
    cp /etc/gtk-3.0/settings.ini "$H/.config/gtk-3.0/settings.ini"
  fi
  src="${RUKE_SRC:-}/overlay/home/.config/gtk-3.0/gtk.css"
  [ -f "$src" ] || src=/etc/skel/.config/gtk-3.0/gtk.css
  if [ -f "$src" ]; then
    cp "$src" "$H/.config/gtk-3.0/gtk.css"
  fi
  if [ -f /usr/share/themes/rukeOS-dark/gtk-2.0/gtkrc ]; then
    printf 'gtk-theme-name = "rukeOS-dark"\ngtk-icon-theme-name = "rukeOS"\ngtk-font-name = "Inter 10"\ninclude "/usr/share/themes/rukeOS-dark/gtk-2.0/gtkrc"\n' > "$H/.gtkrc-2.0"
  fi
  cat > "$H/.config/xsettingsd/xsettingsd.conf" << 'XS'
Net/ThemeName "rukeOS-dark"
Net/IconThemeName "rukeOS"
Gtk/CursorThemeName "Adwaita"
Gtk/FontName "Inter 10"
Gtk/ApplicationPreferDarkTheme 1
Gtk/KeyThemeName "Default"
Xft/Antialias 1
Xft/Hinting 1
Xft/HintStyle "hintslight"
Xft/RGBA "rgb"
XS

  # GTK Default key theme (not Emacs): Ctrl+A is Select all in the text editor.
  if [ -f "$H/.config/gtk-3.0/settings.ini" ]; then
    if grep -q '^gtk-key-theme-name=' "$H/.config/gtk-3.0/settings.ini"; then
      sed -i 's/^gtk-key-theme-name=.*/gtk-key-theme-name=Default/' "$H/.config/gtk-3.0/settings.ini"
    else
      printf '\ngtk-key-theme-name=Default\n' >> "$H/.config/gtk-3.0/settings.ini"
    fi
  fi
  if [ -f "$H/.gtkrc-2.0" ] && ! grep -q 'gtk-key-theme-name' "$H/.gtkrc-2.0"; then
    printf 'gtk-key-theme-name = "Default"\n' | cat - "$H/.gtkrc-2.0" > "$H/.gtkrc-2.0.ruke" && mv -f "$H/.gtkrc-2.0.ruke" "$H/.gtkrc-2.0"
  fi
  # If Mousepad saved an empty Select all accel, restore Ctrl+A (do not add JWM grabs).
  acc="$H/.config/Mousepad/accels.scm"
  if [ -f "$acc" ] && grep -q 'edit.select-all' "$acc"; then
    if grep -q 'gtk_accel_path "<Actions>/win.edit.select-all" ""' "$acc" \
       || grep -q 'gtk_accel_path "<Actions>/win.edit.select-all"$' "$acc"; then
      tmp="$acc.ruke-new"
      sed 's|gtk_accel_path "<Actions>/win.edit.select-all" ""|(gtk_accel_path "<Actions>/win.edit.select-all" "<Control>A")|' "$acc" > "$tmp" && mv -f "$tmp" "$acc"
      chown "$U:$U" "$acc" 2>/dev/null || true
    fi
  fi

  chown -R "$U:$U" "$H/.config/gtk-3.0" "$H/.config/xsettingsd" "$H/.gtkrc-2.0" 2>/dev/null || true
  # Seed animations if the user has no setting yet (512 MB -> reduced).
  if [ -f "$H/.config/rukeos/appearance.conf" ]; then
    grep -q '^animations=' "$H/.config/rukeos/appearance.conf" || {
      kb=$(awk '/MemTotal:/{print $2}' /proc/meminfo 2>/dev/null)
      def=on
      [ -n "$kb" ] && [ "$kb" -lt 768000 ] 2>/dev/null && def=reduced
      printf 'animations=%s\n' "$def" >> "$H/.config/rukeos/appearance.conf"
    }
  fi
fi

# Drop the old JWM bottom tray (replaced by ruke-dock).
strip_bottom_tray() {
  conf=$1
  [ -f "$conf" ] || return 0
  grep -q 'Tray x="0" y="-10"' "$conf" || return 0
  tmp=$conf.ruke-new
  awk '
    /<Tray x="0" y="-10"/ { skip=1 }
    skip && /<\/Tray>/ { skip=0; next }
    skip { next }
    { print }
  ' "$conf" > "$tmp" && mv -f "$tmp" "$conf"
}

if [ -n "$H" ]; then
  for f in "$H/.jwmrc" "$H/.config/jwm/jwmrc"; do
    strip_bottom_tray "$f"
    [ -f "$f" ] && chown "$U:$U" "$f" 2>/dev/null || true
  done
fi

# Autostart: compositor helper + dock.
if [ -n "$H" ] && [ -f "$H/.config/autostart.sh" ]; then
  as=$H/.config/autostart.sh
  if grep -q 'picom -b --config' "$as" && ! grep -q 'ruke-compositor' "$as"; then
    sed -i 's|picom -b --config [^ ]*|command -v ruke-compositor >/dev/null \&\& ruke-compositor || picom -b --config "$HOME/.config/picom/picom.conf"|' "$as"
  fi
  if ! grep -q 'ruke-dock' "$as"; then
    # insert after compositor/picom line
    awk '
      { print }
      /ruke-compositor|picom -b/ && !done { print "command -v ruke-dock >/dev/null && ruke-dock --replace &"; done=1 }
    ' "$as" > "$as.ruke-new" && mv -f "$as.ruke-new" "$as"
    chmod +x "$as"
  fi
  chown "$U:$U" "$as" 2>/dev/null || true
fi

chmod +x /usr/local/bin/ruke-dock /usr/local/bin/ruke-compositor 2>/dev/null || true

# If the desktop is already running, refresh the theme, compositor, and dock.
if [ -n "$U" ]; then
  uid=$(id -u "$U" 2>/dev/null || true)
  if [ -n "$uid" ]; then
    pid=$(pgrep -u "$uid" -x jwm 2>/dev/null | head -n 1 || true)
    if [ -n "$pid" ] && [ -r "/proc/$pid/environ" ]; then
      disp=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^DISPLAY=//p' | head -n 1)
      xauth=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^XAUTHORITY=//p' | head -n 1)
      runtime=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^XDG_RUNTIME_DIR=//p' | head -n 1)
      if [ -n "$disp" ]; then
        run() { sudo -u "$U" -H env DISPLAY="$disp" XAUTHORITY="${xauth:-$H/.Xauthority}" XDG_RUNTIME_DIR="${runtime:-/tmp/runtime-$uid}" HOME="$H" "$@"; }
        run pkill -u "$uid" -HUP -x xsettingsd 2>/dev/null || true
        run ruke-compositor 2>/dev/null || true
        run ruke-dock --replace 2>/dev/null &
      fi
    fi
  fi
fi

exit 0
