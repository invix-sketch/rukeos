#!/bin/sh
# 0.4.2 -> 0.4.3 (runs once). Env: RUKE_USER, RUKE_HOME, RUKE_SRC.
# Drop pack-tile aliases that overrode Papirus folder / file-type icons,
# then refresh icon caches. Theme CSS and new icons come from the system overlay.
set -e

for size in 24x24 48x48 scalable; do
  ext=png
  [ "$size" = scalable ] && ext=svg
  for name in folder inode-directory audio-x-generic video-x-generic; do
    rm -f "/usr/share/icons/rukeOS/$size/apps/$name.$ext"
  done
done

gtk-update-icon-cache -f /usr/share/icons/rukeOS 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
exit 0
