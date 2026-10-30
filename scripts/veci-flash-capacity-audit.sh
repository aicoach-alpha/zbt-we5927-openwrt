#!/bin/sh
# Read-only partition capacity check for ZBT WE5927 General-Cafe firmware.
set -eu
if [ "$#" -gt 1 ]; then echo 'usage: veci-flash-capacity-audit.sh [test-mtd-file]' >&2; exit 2; fi
mtd=/proc/mtd
if [ "$#" -eq 1 ]; then mtd="$1"; fi
if [ ! -r "$mtd" ]; then
  echo 'MTD_GATE=BLOCKED_NO_PARTITION_TABLE'
  exit 2
fi
command -v ubus >/dev/null 2>&1 || { echo 'MTD_GATE=BLOCKED_NO_UBUS'; exit 2; }
command -v jsonfilter >/dev/null 2>&1 || { echo 'MTD_GATE=BLOCKED_NO_JSONFILTER'; exit 2; }
board_data="$(ubus call system board 2>/dev/null)" || {
  echo 'MTD_GATE=BLOCKED_NO_BOARD_IDENTITY'
  exit 2
}
board="$(jsonfilter -s "$board_data" -e '@.board_name' 2>/dev/null || true)"
target="$(jsonfilter -s "$board_data" -e '@.release.target' 2>/dev/null || true)"
printf 'BOARD=%s\nTARGET=%s\n' "$board" "$target"
if [ "$board" != 'zbtlink,zbt-we5927' ] || [ "$target" != 'ramips/mt76x8' ]; then
  echo 'MTD_GATE=BLOCKED_BOARD_TARGET_MISMATCH'
  exit 3
fi

# The source profile limits a candidate image to 7808 KiB.
# This is NOT a substitute for checking the actual sysupgrade image size.
profile_budget=$((7808 * 1024))
printf 'PROFILE_MAX_IMAGE_BYTES=%s\n' "$profile_budget"
printf 'KERNEL=%s\n' "$(uname -r 2>/dev/null || echo UNKNOWN)"
hex="$(awk '$4 == "\"firmware\"" { print $2 }' "$mtd")"
case "$hex" in
  ''|*[!0123456789abcdefABCDEF]*)
    echo 'MTD_GATE=BLOCKED_MISSING_OR_INVALID_FIRMWARE_PARTITION'
    exit 4
    ;;
esac
if [ "$(printf %s "$hex" | wc -c | tr -d ' ')" -gt 8 ]; then
  echo 'MTD_GATE=BLOCKED_INVALID_PARTITION_SIZE'
  exit 4
fi
bytes="$((0x$hex))"
[ "$bytes" -gt 0 ] || {
  echo 'MTD_GATE=BLOCKED_ZERO_CAPACITY'
  exit 4
}
printf 'MTD_FIRMWARE_HEX=%s\nMTD_FIRMWARE_BYTES=%s\n' "$hex" "$bytes"
if [ "$profile_budget" -gt "$bytes" ]; then
  echo 'MTD_GATE=PROFILE_LIMIT_EXCEEDS_REAL_FLASH_PARTITION'
  echo 'FLASH_DECISION=NO_GO'
  exit 5
fi
echo 'MTD_GATE=PROFILE_LIMIT_FITS_REPORTED_PARTITION'
echo 'FLASH_DECISION=NO_GO_UNTIL_IMAGE_VERIFIED_RECOVERY_AND_HARDWARE_UAT'
exit 0
