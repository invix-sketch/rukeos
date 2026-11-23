#!/bin/sh
# every run: compile GSettings schemas so the rukeOS defaults (dark theme etc.) apply
command -v glib-compile-schemas >/dev/null && glib-compile-schemas /usr/share/glib-2.0/schemas
exit 0
