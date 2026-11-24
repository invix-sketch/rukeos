#!/bin/sh
mkdir -p "$HOME/Desktop"
command -v xsettingsd >/dev/null && xsettingsd -c "$HOME/.config/xsettingsd/xsettingsd.conf" &
feh --no-fehbg --bg-fill /usr/share/backgrounds/rukeos.png
command -v pcmanfm >/dev/null && pcmanfm --desktop &
picom -b --config /home/judah/.config/picom/picom.conf
command -v ruke-settings >/dev/null && ruke-settings --apply-session
command -v ruke-autolock >/dev/null && ruke-autolock
if command -v ruke-passwd >/dev/null && [ "$(sudo -n ruke-passwd status 2>/dev/null)" = none ]; then
  command -v ruke-settings >/dev/null && ruke-settings --page security --prompt-password &
fi
sleep 2
command -v ruke-update-notify >/dev/null && ruke-update-notify &
exec xterm -T "Welcome to rukeOS" -geometry 74x19 -e sh -c "fastfetch; exec bash"
