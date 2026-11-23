#!/bin/sh
# Point this repo at another GitHub account/repo:  ./set-owner.sh NEWOWNER [REPO]
[ -n "$1" ] || { echo "usage: $0 NEWOWNER [REPO]"; exit 1; }
old=$(sed -n 's/^RUKE_OWNER="\(.*\)"/\1/p' overlay/system/etc/rukeos/update.conf)
sed -i "s#$old#$1#g" overlay/system/etc/rukeos/update.conf install.sh README.md overlay/system/usr/local/bin/ruke-update
[ -n "$2" ] && sed -i "s#RUKE_REPO=\"rukeos\"#RUKE_REPO=\"$2\"#; s#RUKE_REPO:-rukeos#RUKE_REPO:-$2#; s#/rukeos/main#/$2/main#g" overlay/system/etc/rukeos/update.conf install.sh README.md overlay/system/usr/local/bin/ruke-update
echo "owner: $old -> $1"; grep -rn "$1" --include=* . | grep -v '^./.git' | head
