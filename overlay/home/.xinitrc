export NO_AT_BRIDGE=1
export GTK2_RC_FILES="${GTK2_RC_FILES:-$HOME/.gtkrc-2.0}"
xsetroot -solid '#1a1b26' -cursor_name left_ptr
[ -f ~/.Xresources ] && xrdb -merge ~/.Xresources
exec dbus-launch --exit-with-session jwm
