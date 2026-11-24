#!/bin/sh
# every run: if an icon-theme upgrade brought back the big sizes rukeOS removes, drop them again (saves ~40 MB)
rm -rf /usr/share/icons/ePapirus /usr/share/icons/ePapirus-Dark /usr/share/icons/Papirus-Light
if [ -d /usr/share/icons/Papirus/64x64 ] || [ -d /usr/share/icons/Papirus-Dark/64x64 ]; then
  for d in 64x64 64x64@2x 84x84 96x96 128x128 48x48@2x 32x32@2x 24x24@2x 22x22@2x 18x18@2x 16x16@2x; do
    rm -rf /usr/share/icons/Papirus/$d /usr/share/icons/Papirus-Dark/$d; done
  gtk-update-icon-cache -f /usr/share/icons/Papirus; gtk-update-icon-cache -f /usr/share/icons/Papirus-Dark
fi
gtk-update-icon-cache -f /usr/share/icons/rukeOS 2>/dev/null || true
exit 0
