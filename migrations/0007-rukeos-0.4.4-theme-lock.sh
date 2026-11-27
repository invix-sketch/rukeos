#!/bin/sh
# 0.4.3 -> 0.4.4 (runs once). Env: RUKE_USER, RUKE_HOME, RUKE_SRC.
# 0.4.3's rukeOS-dark gtk.css @imported Adwaita-dark as a GTK resource. If that
# import failed (common on Alpine), GTK threw the whole theme away and fell back
# to Adwaita light — which is why Files and Settings still looked white after
# a successful 0.4.3 OTA. Forcibly re-point user + system theme configs and
# refresh the lock background.
set -e
H="${RUKE_HOME:-}"
U="${RUKE_USER:-}"

write_settings_ini() {
  dest=$1
  mkdir -p "$(dirname "$dest")"
  cat > "$dest" << 'INI'
[Settings]
gtk-theme-name=rukeOS-dark
gtk-application-prefer-dark-theme=1
gtk-icon-theme-name=rukeOS
gtk-font-name=Inter 10
gtk-cursor-theme-name=Adwaita
gtk-xft-antialias=1
gtk-xft-hinting=1
gtk-xft-hintstyle=hintslight
gtk-xft-rgba=rgb
INI
}

# System-wide (in case an older ISO image is missing them)
mkdir -p /etc/gtk-3.0 /etc/gtk-2.0 /etc/skel/.config/gtk-3.0 /etc/skel/.config/xsettingsd
write_settings_ini /etc/gtk-3.0/settings.ini
write_settings_ini /etc/skel/.config/gtk-3.0/settings.ini
if [ -f /usr/share/themes/rukeOS-dark/gtk-2.0/gtkrc ]; then
  cat > /etc/gtk-2.0/gtkrc << 'G2'
gtk-theme-name = "rukeOS-dark"
gtk-icon-theme-name = "rukeOS"
gtk-font-name = "Inter 10"
include "/usr/share/themes/rukeOS-dark/gtk-2.0/gtkrc"
G2
  cp /etc/gtk-2.0/gtkrc /etc/skel/.gtkrc-2.0
fi

# Confirm the packaged theme no longer has a failing Adwaita @import
# (overlay already replaced the file; this is a safety strip).
css=/usr/share/themes/rukeOS-dark/gtk-3.0/gtk.css
if [ -f "$css" ] && grep -q 'resource:///org/gtk/libgtk/theme/Adwaita/' "$css"; then
  tmp=$(mktemp)
  grep -v 'resource:///org/gtk/libgtk/theme/Adwaita/' "$css" | grep -v '@import url' > "$tmp" || true
  mv -f "$tmp" "$css"
fi

if [ -n "$H" ]; then
  mkdir -p "$H/.config/gtk-3.0" "$H/.config/xsettingsd" "$H/.config/jgmenu"
  write_settings_ini "$H/.config/gtk-3.0/settings.ini"
  # Refresh user gtk.css hole-fixes from the packaged copy when present
  src="${RUKE_SRC:-}/overlay/home/.config/gtk-3.0/gtk.css"
  [ -f "$src" ] || src=/etc/skel/.config/gtk-3.0/gtk.css
  if [ -f "$src" ]; then
    cp "$src" "$H/.config/gtk-3.0/gtk.css"
  fi
  cat > "$H/.config/xsettingsd/xsettingsd.conf" << 'XS'
Net/ThemeName "rukeOS-dark"
Net/IconThemeName "rukeOS"
Gtk/CursorThemeName "Adwaita"
Gtk/FontName "Inter 10"
Gtk/ApplicationPreferDarkTheme 1
Xft/Antialias 1
Xft/Hinting 1
Xft/HintStyle "hintslight"
Xft/RGBA "rgb"
XS
  if [ -f /usr/share/themes/rukeOS-dark/gtk-2.0/gtkrc ]; then
    cat > "$H/.gtkrc-2.0" << 'G2'
gtk-theme-name = "rukeOS-dark"
gtk-icon-theme-name = "rukeOS"
gtk-font-name = "Inter 10"
include "/usr/share/themes/rukeOS-dark/gtk-2.0/gtkrc"
G2
  fi
  # menu: App store + windows-apps include (menu.csv is refreshed by the overlay
  # on a version bump; still patch if this ran without a home refresh)
  menu="$H/.config/jgmenu/menu.csv"
  if [ -f "$menu" ]; then
    awk -v home="$H" '
      BEGIN { store="App store,ruke-appstore,/usr/share/icons/hicolor/24x24/apps/ruke-app-menu.png" }
      { all = all $0 "\n" }
      END {
        if (all !~ /ruke-appstore/) sub(/Settings,ruke-settings,/, store "\nSettings,ruke-settings,", all)
        inc="^include(" home "/.config/jgmenu/windows-apps.csv)"
        if (all !~ /windows-apps\.csv/) sub(/\^sep\(System\)/, inc "\n^sep(System)", all)
        printf "%s", all
      }
    ' "$menu" > "$menu.ruke-new" && mv -f "$menu.ruke-new" "$menu"
  fi
  [ -f "$H/.config/jgmenu/windows-apps.csv" ] || printf '^sep(Windows apps)\n' > "$H/.config/jgmenu/windows-apps.csv"
  if [ -n "$U" ]; then
    chown -R "$U:$U" "$H/.config/gtk-3.0" "$H/.config/xsettingsd" "$H/.config/jgmenu" "$H/.gtkrc-2.0" 2>/dev/null || true
  fi
  # Reload the running theme daemon so the new name takes effect before the next login
  if [ -n "$U" ] && command -v xsettingsd >/dev/null; then
    pkill -u "$U" -HUP -x xsettingsd 2>/dev/null || true
  fi
fi

gtk-update-icon-cache -f /usr/share/icons/rukeOS 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
exit 0
