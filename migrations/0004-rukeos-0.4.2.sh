#!/bin/sh
# 0.4.1 -> 0.4.2 (runs once). Env: RUKE_USER, RUKE_HOME, RUKE_SRC.
# Seed desktop + merge pcmanfm desktop settings without clobbering user files.
set -e
H="${RUKE_HOME:-}"
U="${RUKE_USER:-}"
[ -n "$H" ] || exit 0
mkdir -p "$H/Desktop"

# Shortcuts: copy only if that filename is not already there
skel="${RUKE_SRC:-}/overlay/system/usr/share/rukeos/desktop-skel"
[ -d "$skel" ] || skel=/usr/share/rukeos/desktop-skel
if [ -d "$skel" ]; then
  for f in "$skel"/*.desktop; do
    [ -f "$f" ] || continue
    dest="$H/Desktop/$(basename "$f")"
    if [ ! -e "$dest" ]; then
      cp "$f" "$dest"
      chmod +x "$dest"
    fi
  done
fi

# pcmanfm desktop section: add if missing; do not overwrite an existing [desktop]
conf="$H/.config/pcmanfm/default/pcmanfm.conf"
mkdir -p "$(dirname "$conf")"
wp=/usr/share/backgrounds/rukeos.png
if [ -f "$H/.config/rukeos/appearance.conf" ]; then
  w=$(awk -F= '/^wallpaper=/{print $2}' "$H/.config/rukeos/appearance.conf" | tail -1)
  [ -n "$w" ] && [ -f "$w" ] && wp=$w
fi
if [ ! -f "$conf" ] || ! grep -q '^\[desktop\]' "$conf"; then
  printf '\n[desktop]\nwallpaper_mode=crop\nwallpaper=%s\ndesktop_bg=#1a1b26\ndesktop_fg=#c0caf5\ndesktop_shadow=#16161e\ndesktop_font=Inter 10\nshow_wm_menu=1\nsort=name;ascending;\nshow_documents=0\nshow_trash=0\nshow_mounts=0\n' "$wp" >> "$conf"
fi

# Bookmark the Desktop folder if it is not already there
bm="$H/.config/gtk-3.0/bookmarks"
mkdir -p "$(dirname "$bm")"
touch "$bm"
grep -q '/Desktop' "$bm" || sed -i "1i file://$H/Desktop Desktop" "$bm"

if [ -n "$U" ]; then
  chown -R "$U:$U" "$H/Desktop" "$H/.config/pcmanfm" "$H/.config/gtk-3.0/bookmarks" 2>/dev/null || true
fi

# Icon caches so PCManFM picks up the rukeOS theme
gtk-update-icon-cache -f /usr/share/icons/rukeOS 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
exit 0
