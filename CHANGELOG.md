# rukeOS changelog

## 0.3
- Fix "Saving between boots" on sticks where the partition table went missing after flashing (0 MB free): `fix-saving.sh` / new `rukeos-persistence` rebuilds the table (boot code untouched) and adds the save partition.
- `lsblk` added; `RUKE_BRANCH` is remembered by install.sh.
- Real web browser: GNOME Web (WebKitGTK), dark theme, on the dock and menu (`ruke-browser`). NetSurf stays as "Lite Browser".
- `ruke-update`: update rukeOS from this repo without reflashing (+ "Check for updates" in the menu, daily check at login).
- Extra Wi-Fi/Bluetooth firmware: Realtek rtw88/rtw89, MediaTek mt76/mt79xx, Qualcomm ath11k, Bluetooth (Realtek/Qualcomm).
- The kernel is pinned so updates can't break Wi-Fi/graphics drivers.

## 0.2
- First flashed release: persistence ("Saving between boots"), Tokyo Night look, NetSurf.
