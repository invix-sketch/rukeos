export NO_AT_BRIDGE=1
xsetroot -solid '#1a1b26' -cursor_name left_ptr
[ -f ~/.Xresources ] && xrdb -merge ~/.Xresources
exec dbus-launch --exit-with-session jwm
