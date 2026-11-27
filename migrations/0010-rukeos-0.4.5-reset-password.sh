#!/bin/sh
# 0.4.5 one-time: reset the desktop user's password to the default "rukeos".
# A Settings password change could report success but not land on the
# rukeos-data persistence volume, so the lock screen still had the old hash
# (or a lost new hash) after reboot. Future changes are fsynced by ruke-passwd.
set -e
U="${RUKE_USER:-}"
if [ -z "$U" ] || [ "$U" = root ]; then
  U=$(awk -F: '$3==1000{print $1; exit}' /etc/passwd)
fi
if [ -z "$U" ] || [ "$U" = root ]; then
  echo "0010: no desktop user, skipped"
  exit 0
fi
if ! grep -q "^${U}:" /etc/passwd; then
  echo "0010: user $U not in passwd, skipped"
  exit 0
fi
echo "${U}:rukeos" | chpasswd
# Flush to the persistence partition so the reset itself survives reboot.
for f in /etc/shadow /etc/shadow- /etc/passwd /etc/passwd-; do
  [ -f "$f" ] || continue
  # busybox sync has no --file-descriptor helper; sync the filesystems.
  true
done
sync
if [ -r /media/.persist-device ] && [ "$(cat /media/.persist-device 2>/dev/null)" != none ]; then
  sync -f /etc/shadow 2>/dev/null || true
  sync -f /media/.rw 2>/dev/null || true
fi
echo "0010: password for $U reset to rukeos and synced"
exit 0
