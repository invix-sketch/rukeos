#!/bin/sh
# rukeOS updater installer. On rukeOS (0.2 or newer), in the terminal:
#   wget -qO- https://raw.githubusercontent.com/invix-sketch/rukeos/main/install.sh | sudo sh
# It installs the `ruke-update` command, then runs it once (browser, Wi-Fi firmware, theme files...).
RUKE_OWNER=${RUKE_OWNER:-invix-sketch}     # <- the only place to change the GitHub owner here
RUKE_REPO=${RUKE_REPO:-rukeos}; RUKE_BRANCH=${RUKE_BRANCH:-main}
RAW=${RUKE_RAW:-https://raw.githubusercontent.com/$RUKE_OWNER/$RUKE_REPO/$RUKE_BRANCH}
set -e
echo "==> rukeOS updater installer"
[ "$(id -u)" = 0 ] || { echo "Please run with sudo:  wget -qO- $RAW/install.sh | sudo sh"; exit 1; }
grep -q '^ID=rukeos' /etc/os-release 2>/dev/null || { echo "This is not rukeOS - stopping."; exit 1; }
mkdir -p /etc/rukeos /usr/local/bin
wget -q -T 30 -O /usr/local/bin/ruke-update.new "$RAW/overlay/system/usr/local/bin/ruke-update" \
  || { echo "Download failed. Are you online? (dock > network icon, or run: nmtui)"; exit 1; }
head -1 /usr/local/bin/ruke-update.new | grep -q '^#!/bin/sh' || { echo "Downloaded file looks wrong."; exit 1; }
chmod 755 /usr/local/bin/ruke-update.new && mv -f /usr/local/bin/ruke-update.new /usr/local/bin/ruke-update
wget -q -T 30 -O /etc/rukeos/update.conf "$RAW/overlay/system/etc/rukeos/update.conf" || true
# remember non-default sources (forks, local test servers) separately so updates never overwrite them
: > /etc/rukeos/update.local.conf
[ -n "$RUKE_RAW" ] && echo "RUKE_RAW=\"$RUKE_RAW\"" >> /etc/rukeos/update.local.conf
[ -n "$RUKE_TARBALL" ] && echo "RUKE_TARBALL=\"$RUKE_TARBALL\"" >> /etc/rukeos/update.local.conf
[ "$RUKE_OWNER" != invix-sketch ] && echo "RUKE_OWNER=\"$RUKE_OWNER\"" >> /etc/rukeos/update.local.conf
echo "==> ruke-update installed. Running the first update (this downloads ~100 MB, a few minutes)..."
exec /usr/local/bin/ruke-update --yes "$@"
