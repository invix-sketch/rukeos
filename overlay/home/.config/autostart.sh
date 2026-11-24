#!/bin/sh
feh --no-fehbg --bg-fill /usr/share/backgrounds/rukeos.png
picom -b --config /home/judah/.config/picom/picom.conf
command -v ruke-settings >/dev/null && ruke-settings --apply-session
sleep 2
command -v ruke-update-notify >/dev/null && ruke-update-notify &
exec xterm -T "Welcome to rukeOS" -geometry 74x19 -e sh -c "fastfetch; exec bash"
