[ -f ~/.bashrc ] && . ~/.bashrc
# no logind on rukeOS: make the per-user runtime dir ourselves (WebKit sandbox, dbus, portals use it)
if [ -z "$XDG_RUNTIME_DIR" ]; then export XDG_RUNTIME_DIR=/tmp/runtime-$(id -u); mkdir -p -m 700 "$XDG_RUNTIME_DIR"; fi
if [ -z "$DISPLAY" ] && [ "$(tty)" = /dev/tty1 ]; then
  exec startx >/tmp/startx.log 2>&1
fi
