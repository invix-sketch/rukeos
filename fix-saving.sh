#!/bin/sh
# rukeOS: fix "Saving between boots" (Not enough free space / 0 MB free) without reflashing.
#   wget -qO- https://raw.githubusercontent.com/invix-sketch/rukeos/main/fix-saving.sh | sudo sh
# Installs the fixed rukeos-persistence tool, repairs the stick's partition table if it is
# missing (keeps the boot code and the rukeOS system as they are), adds the save partition
# in the free space, formats it, and tells you to reboot. Nothing is asked; safe to pipe.
echo "==> rukeOS: fixing Saving between boots"
[ "$(id -u)" = 0 ] || { echo "Please run with sudo:  wget -qO- https://raw.githubusercontent.com/invix-sketch/rukeos/main/fix-saving.sh | sudo sh"; exit 1; }
grep -q '^ID=rukeos' /etc/os-release 2>/dev/null || { echo "This is not rukeOS - stopping."; exit 1; }
mkdir -p /usr/local/bin
cat > /usr/local/bin/rukeos-persistence.new <<'RUKE_TOOL_EOF'
#!/bin/sh
# rukeOS persistence ("saving between boots") helper - v2 (works on sticks where the
# partition table was missing/damaged after flashing, e.g. kernel shows only /dev/sdX).
#   rukeos-persistence            show status, offer to enable
#   rukeos-persistence --yes      enable without asking
LABEL=rukeos-data
say() { printf '%s\n' "$*"; }
die() { say "!! $*"; exit 1; }
[ "$(id -u)" = 0 ] || exec sudo "$0" "$@"

cur=$(cat /media/.persist-device 2>/dev/null)
if [ -n "$cur" ] && [ "$cur" != none ]; then
  say "Saving between boots is ON  (stored on $cur)."
  df -h /media/.rw | tail -1 | awk '{print "Space used: "$3" of "$2" ("$5")"}'
  say "Boot the 'fresh session' menu entry to start without your saved changes."
  exit 0
fi
existing=$(blkid -L "$LABEL" 2>/dev/null)
[ -n "$existing" ] && { say "A save partition already exists ($existing). Reboot to start using it."; exit 0; }

src=$(awk '$2=="/media/live"{print $1}' /proc/mounts)
case "$src" in
  /dev/sr*|"") say "rukeOS was started from a CD/DVD (or a VM cdrom), which can't store anything."
               say "Write the ISO to a USB stick (Rufus 'DD image' mode) and run this again."; exit 1;;
esac
b=$(basename "$src")
[ -e /sys/class/block/$b/partition ] && b=$(basename "$(readlink -f /sys/class/block/$b/..)")
disk=/dev/$b
total=$(cat /sys/block/$b/size)                        # always in 512-byte units
ss=$(cat /sys/block/$b/queue/logical_block_size 2>/dev/null || echo 512)
[ "$ss" = 512 ] || die "This stick uses $ss-byte sectors, which this tool can't handle yet."

u8()  { dd if="$disk" bs=1 skip="$1" count=1 2>/dev/null | od -An -tu1 | tr -d ' \n'; }
u32() { dd if="$disk" bs=1 skip="$1" count=4 2>/dev/null | od -An -tu4 | tr -d ' \n'; }
str() { dd if="$disk" bs=1 skip="$1" count="$2" 2>/dev/null; }
# little-endian 32-bit value -> printf escape string
le32() { v=$1; o=; for i in 1 2 3 4; do o="$o\\0$(printf %03o $((v & 255)))"; v=$((v >> 8)); done; printf %s "$o"; }
wb() { printf '%b' "$1"; }   # write bytes given as \0NNN escapes

# ---- 1. where does the rukeOS image end? (ISO9660 volume size + partition table) ----
iso_end=0
[ "$(str 32769 5)" = CD001 ] && iso_end=$(( $(u32 32848) * 4 ))      # whole-disk ISO header
p1iso=0
[ "$(str 65537 5)" = CD001 ] && p1iso=$(( $(u32 65616) * 4 ))        # ISO inside partition 1 (offset 64)
gpt=0; sfdisk -d "$disk" 2>/dev/null | grep -q '^label: gpt' && gpt=1
kparts=$(ls -d /sys/block/$b/$b* 2>/dev/null | wc -l)                # partitions the kernel accepted
sig=$(u32 508); sig=$(( (sig >> 16) & 65535 ))                      # bytes 510-511
tab_end=0; slots=; bad=0
for i in 0 1 2 3; do
  o=$((446 + 16 * i)); t=$(u8 $((o + 4))); s=$(u32 $((o + 8))); n=$(u32 $((o + 12)))
  if [ "$t" = 238 ]; then                                            # GPT-protective entry
    { [ $gpt = 0 ] || [ "$kparts" = 0 ]; } && bad=1                  # ...but no GPT the kernel accepts
    :
  elif [ "$t" = 131 ] && [ $iso_end -gt 0 ] && [ "$s" -ge $iso_end ]; then :   # our own save partition from an earlier run
  elif [ "$t" != 0 ] && [ "$n" -gt 0 ]; then e=$((s + n)); [ $e -gt $tab_end ] && tab_end=$e; fi
  slots="$slots $t:$s:$n"
done
[ "$sig" = 43605 ] || bad=1                                          # 0xAA55 missing
[ "$kparts" = 0 ] && [ $tab_end -gt 0 ] && [ $tab_end -ge $((total - 2048)) ] && bad=1   # ignored table covering the whole stick
[ $bad = 1 ] && { gpt=0; tab_end=0; }
last=$iso_end; [ $tab_end -gt $last ] && last=$tab_end
[ $gpt = 1 ] && { g=$(sfdisk -d "$disk" 2>/dev/null | awk -F'[=,]' '/start=/{s=$2+0; z=$4+0; if (s+z>m) m=s+z} END{print m+0}'); [ "${g:-0}" -gt $last ] && last=$g; }
[ "$last" -gt 0 ] || die "Could not find where the rukeOS image ends on $disk - stopping, nothing was changed."
mib=2048
start=$(( (last + 2 * mib - 1) / mib * mib ))                        # next MiB boundary + >=1 MiB gap
size=$(( total - start - 2048 ))                                     # leave 1 MiB at the end
[ $size -gt 4294967295 ] && size=4294967295
free_mb=$(( size / 2048 ))
say "USB drive: $disk   total $(( total / 2048 )) MB, rukeOS image ends at $(( last / 2048 )) MB, free: ${free_mb} MB"
[ "$free_mb" -ge 128 ] || die "Not enough free space (need 128 MB+). Use a bigger USB stick."

if [ "$1" != "--yes" ]; then
  say ""; say "This creates a new partition '$LABEL' in the free space of $disk and formats it."
  say "Your rukeOS system on the stick is not touched. Continue? [y/N]"
  read -r a </dev/tty; case "$a" in y|Y|yes) ;; *) say "Cancelled."; exit 1;; esac
fi
set -e
bk=/root/rukeos-mbr-backup-$(date +%Y%m%d-%H%M%S).bin
dd if="$disk" of="$bk" bs=512 count=1 2>/dev/null; sync

# ---- 2a. real GPT: old method (sfdisk) ----
if [ $gpt = 1 ]; then
  sfdisk -q --relocate gpt-bak-std "$disk"
  before=$(sfdisk -d "$disk" | grep -c 'start=')
  printf 'start=%s, type=L, name=%s\n' "$start" "$LABEL" | sfdisk -q --append --no-reread --no-tell-kernel "$disk"
  n=$((before + 1))
else
# ---- 2b. MBR: write the entries directly, keeping the boot code (bytes 0-445) untouched ----
  if [ $bad = 1 ] || [ $tab_end = 0 ]; then
    say "The partition table on $disk is missing or damaged (that's why saving couldn't find free space)."
    [ $p1iso -gt 0 ] || die "Can't rebuild it safely (no rukeOS image found at the expected place). Nothing was changed."
    esp=$((64 + p1iso))
    [ "$(str $((esp * 512 + 510)) 2 | od -An -tx1 | tr -d ' \n')" = 55aa ] || die "EFI boot area not found where expected. Nothing was changed."
    esz=$(( $(dd if="$disk" bs=1 skip=$((esp * 512 + 19)) count=2 2>/dev/null | od -An -tu2 | tr -d ' \n') ))
    [ "$esz" -gt 0 ] || esz=$(( $(u32 $((esp * 512 + 32))) ))
    [ $((esp + esz)) -gt $last ] && last=$((esp + esz)) && start=$(( (last + 2 * mib - 1) / mib * mib )) && size=$(( total - start - 2048 ))
    say "Rebuilding it the way the rukeOS image had it: system $((64)):$p1iso, EFI boot $esp:$esz."
    slots=" 205:64:$p1iso 239:$esp:$esz 0:0:0 0:0:0"
    # entries 1+2 (bootable 0xCD ISO partition + 0xEF EFI partition), clear 3+4
    { wb "\0200\0376\0377\0377\0315\0376\0377\0377$(le32 64)$(le32 $p1iso)";
      wb "\0000\0376\0377\0377\0357\0376\0377\0377$(le32 $esp)$(le32 $esz)";
      dd if=/dev/zero bs=32 count=1 2>/dev/null; wb '\0125\0252'; } > /tmp/.mbr-tail
    dd if=/tmp/.mbr-tail of="$disk" bs=1 seek=446 conv=notrunc 2>/dev/null
  fi
  n=0; i=1
  for sl in $slots; do
    t=${sl%%:*}; r=${sl#*:}; s=${r%%:*}
    if [ "$t" = 131 ] && [ "$s" -ge "$last" ]; then n=$i; start=$s; break; fi   # already added earlier
    [ "$t" = 0 ] && [ $n = 0 ] && n=$i
    i=$((i + 1))
  done
  [ $n -gt 0 ] || die "No free slot in the partition table (4 used). Nothing was changed."
  wb "\0000\0376\0377\0377\0203\0376\0377\0377$(le32 $start)$(le32 $size)" > /tmp/.mbr-p
  dd if=/tmp/.mbr-p of="$disk" bs=1 seek=$((446 + 16 * (n - 1))) conv=notrunc 2>/dev/null
  wb '\0125\0252' | dd of="$disk" bs=1 seek=510 conv=notrunc 2>/dev/null
  rm -f /tmp/.mbr-p /tmp/.mbr-tail
fi
sync

# ---- 3. format it (through the new partition if the kernel shows it, else through a loop device) ----
partx -a -n $n "$disk" 2>/dev/null || true
case "$b" in nvme*|mmcblk*|loop*) part=${disk}p$n;; *) part=$disk$n;; esac
for i in 1 2 3 4 5 6; do [ -b "$part" ] && break; sleep 0.5; done
set +e; dev=
if [ -b "$part" ] && [ "$(cat /sys/class/block/$(basename $part)/start 2>/dev/null)" = "$start" ]; then
  # -F -F: the stick itself is mounted (rukeOS runs from it); the new partition is not
  mkfs.ext4 -q -F -F -L "$LABEL" -m 1 "$part" 2>/dev/null && dev=$part
fi
if [ -z "$dev" ]; then
  lo=$(losetup -f) && losetup -o $((start * 512)) "$lo" "$disk" || die "Could not attach the new area."
  mkfs.ext4 -q -F -F -L "$LABEL" -m 1 -b 4096 "$lo" $((size / 8)) || { losetup -d "$lo"; die "Formatting failed."; }
  sync; losetup -d "$lo"; dev="$disk (partition $n, visible after reboot)"
fi
sync
say ""
say "Done! Saving between boots is set up on $dev."
say "(Old partition table saved to $bk until reboot.)"
say "REBOOT NOW - from the next start, files, settings and installed apps are kept."
RUKE_TOOL_EOF
chmod 755 /usr/local/bin/rukeos-persistence.new && mv -f /usr/local/bin/rukeos-persistence.new /usr/local/bin/rukeos-persistence
/usr/local/bin/rukeos-persistence --yes </dev/null
rc=$?
if [ $rc = 0 ]; then
  echo ""
  echo "Next: reboot (sudo reboot). After it starts, run the updater once more WITHOUT --allow-ram:"
  echo "  wget -qO- https://raw.githubusercontent.com/invix-sketch/rukeos/main/install.sh | sudo sh"
fi
exit $rc
