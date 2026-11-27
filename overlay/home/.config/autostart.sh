#!/bin/sh
mkdir -p "$HOME/Desktop"
command -v xsettingsd >/dev/null && xsettingsd -c "$HOME/.config/xsettingsd/xsettingsd.conf" &
feh --no-fehbg --bg-fill /usr/share/backgrounds/rukeos.png
command -v pcmanfm >/dev/null && pcmanfm --desktop &
command -v ruke-compositor >/dev/null && ruke-compositor || picom -b --config "$HOME/.config/picom/picom.conf"
command -v ruke-dock >/dev/null && ruke-dock --replace &
command -v ruke-settings >/dev/null && ruke-settings --apply-session
command -v dunst >/dev/null && dunst &
command -v ruke-clipboard >/dev/null && ruke-clipboard --daemon &
command -v udiskie >/dev/null && udiskie --automount --notify --no-tray &
command -v ruke-notify-watch >/dev/null && ruke-notify-watch &
command -v ruke-autolock >/dev/null && ruke-autolock
if command -v ruke-passwd >/dev/null && [ "$(sudo -n ruke-passwd status 2>/dev/null)" = none ]; then
  command -v ruke-settings >/dev/null && ruke-settings --page security --prompt-password &
fi
sleep 2
command -v ruke-update-notify >/dev/null && ruke-update-notify &
exec xterm -T "Welcome to rukeOS" -geometry 74x19 -e sh -c "fastfetch; exec bash"
