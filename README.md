# rukeOS updates

This repo keeps a rukeOS USB stick up to date **without reflashing**: new apps, Wi-Fi firmware,
theme/dock/menu changes and fixes all come from here.

## First time (on rukeOS 0.2)

1. Turn on **Saving between boots** (menu > Saving between boots, then reboot) - otherwise the update is gone after a reboot.
2. Get online: dock > network icon (or run `nmtui`) > *Activate a connection* > your Wi-Fi.
3. Open a terminal and run:

```sh
wget -qO- https://raw.githubusercontent.com/invix-sketch/rukeos/main/install.sh | sudo sh
```

That installs the `ruke-update` command and runs the first update (downloads about 150 MB; takes a few minutes).
When it says *Update finished*, pick **menu > Restart desktop**. The dock's globe icon is now a full web browser.

## After that

- **menu > Check for updates**, or run `ruke-update` in a terminal.
- rukeOS also checks once a day after you log in and asks before installing anything.

| command | what it does |
|---|---|
| `ruke-update` | check, ask, then update everything |
| `ruke-update --yes` | update without asking |
| `ruke-update --check` | only say if a new rukeOS version is out |
| `ruke-update --force` | re-apply the rukeOS files even if already up to date |
| `ruke-update --no-upgrade` | skip the `apk upgrade` of system packages |

Log: `/var/log/ruke-update.log`. If an update changes one of your desktop files (like `~/.jwmrc`),
your old copy is saved in `~/.local/share/ruke-update/backup/<date>/`.

## What an update does

1. Reads `VERSION` here and compares it with `/etc/rukeos/version`.
2. Downloads this repo as a tarball.
3. `apk update && apk upgrade` (the kernel is pinned: it comes from the USB stick, so apk never replaces it).
4. Installs everything in `packages.txt`, removes what's in `remove.txt`.
5. Copies `overlay/system/` to `/` and `overlay/home/` to `/home/<user>/`.
6. Runs each script in `migrations/` once (remembered in `/var/lib/rukeos/migrations.done`), then every script in `hooks/`.
7. Writes the new version to `/etc/rukeos/version` and `/etc/os-release`, and prints a summary.

## Repo layout

```
VERSION                 current rukeOS version (bump it to ship an update)
install.sh              first-time installer (the wget one-liner)
packages.txt            apk packages every rukeOS should have
remove.txt              apk packages to remove
overlay/system/         files copied to /  (ruke-update itself lives in usr/local/bin/)
overlay/home/           files copied to the user's home (dock, menu, theme)
migrations/NNNN-*.sh    run once per machine, in order
hooks/*.sh              run after every update
set-owner.sh            point everything at another GitHub owner: ./set-owner.sh NAME
```

## Shipping an update (for the maintainer)

Change files, bump `VERSION` (e.g. `0.3` -> `0.3.1`), commit, push to `main`.
Every rukeOS stick sees it the next time it checks. Keep this repo public and **never put passwords or tokens in it**.

The GitHub owner is set in one variable per file: `RUKE_OWNER` in `overlay/system/etc/rukeos/update.conf`
and in `install.sh` (`./set-owner.sh NEWNAME` changes both). Testing against another server:
`wget -qO- http://HOST/install.sh | sudo RUKE_RAW=http://HOST RUKE_TARBALL=http://HOST/main.tar.gz sh`
(saved in `/etc/rukeos/update.local.conf`; delete that file to go back to GitHub).

## Limits

- Needs internet. If your Wi-Fi card has no firmware in 0.2 (Realtek RTL8821CE/8822CE/8852, MediaTek, Qualcomm WCN6855),
  get online with an Ethernet cable or **USB tethering from a phone** first; the update then adds that firmware.
- The Linux kernel itself can't be updated this way (it lives on the stick); that needs a new ISO.
- Reflashing the stick with a new ISO also wipes the *Saving between boots* partition, so copy your files off first.
