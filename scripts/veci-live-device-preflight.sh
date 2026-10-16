#!/bin/sh
# WE5927 READ-ONLY device facts for operator UAT. NO AT, SMS/USSD,
# sysupgrade, package install, reboot, network changes, or secret output.
# Checks hardware facts; NEVER grants flash permission. GPL-2.0-only.
set -eu
LC_ALL=C
export LC_ALL
[ "$#" -eq 0 ] || { echo "usage: veci-live-device-preflight.sh" >&2; exit 2; }
# Fixture mode is for HOST TESTS ONLY; NEVER use its output as LIVE evidence.
if [ "${VECI_OFFLINE_FIXTURE:-}" = 1 ]; then
    root="${VECI_TEST_ROOT:-}"
    [ -n "$root" ] && [ -d "$root/sys" ] || exit 2
    evidence=OFFLINE_FIXTURE
else
    root=''
    evidence=PHYSICAL_READ_ONLY
fi
path() { printf '%s%s' "$root" "$1"; }
board="$(cat "$(path /tmp/sysinfo/board_name)" 2>/dev/null || :)"
case "$board" in
    zbtlink,zbt-we5927) board_ok=1 ;;
    *) board_ok=0 ;;
esac
kernel="$(cat "$(path /proc/sys/kernel/osrelease)" 2>/dev/null || :)"
case "$kernel" in
    6.*) kernel_ok=1 ;;
    *) kernel_ok=0 ;;
esac
[ -s "$(path /proc/mtd)" ] && flash_ok=1 || flash_ok=0
[ -f "$(path /etc/openwrt_release)" ] && os_ok=1 || os_ok=0
[ -x "$(path /sbin/sysupgrade)" ] && upgrader_ok=1 || upgrader_ok=0
[ -f "$(path /etc/config/network)" ] && network_ok=1 || network_ok=0
[ -f "$(path /etc/config/wireless)" ] && wireless_ok=1 || wireless_ok=0
[ -d "$(path /www/luci-static)" ] && luci_ok=1 || luci_ok=0
usb_ok=0
# Match only fixed sysfs AT interface 1.4 and USB 05c6:902e.
# Do not open/probe any tty and NEVER try ttyUSB3.
for t in "$(path /sys/class/tty)"/ttyUSB*; do
    [ -e "$t/device" ] || continue
    name="${t##*/}"
    [ "$name" != ttyUSB3 ] || continue
    case "$name" in ttyUSB[0-9]|ttyUSB[0-9][0-9]) ;; *) continue ;; esac
    devpath="$(readlink -f "$t/device" 2>/dev/null || :)"
    case "$devpath" in
        "$(path /sys/devices)"/*:1.4/*)
            ifdir="${devpath%/*}"
            parent="${ifdir%/*}"
            v="$(cat "$parent/idVendor" 2>/dev/null || :)"
            p="$(cat "$parent/idProduct" 2>/dev/null || :)"
            if [ "$v" = 05c6 ] && [ "$p" = 902e ]; then
                usb_ok=1
                break
            fi
            ;;
    esac
done
printf 'evidence=%s\n' "$evidence"
printf 'board_check=%s\n' "$board_ok"
printf 'kernel_check=%s\n' "$kernel_ok"
printf 'flash_partition_present=%s\n' "$flash_ok"
printf 'openwrt_release_present=%s\n' "$os_ok"
printf 'updater_present=%s\n' "$upgrader_ok"
printf 'network_config_present=%s\n' "$network_ok"
printf 'wireless_config_present=%s\n' "$wireless_ok"
printf 'luci_fallback_present=%s\n' "$luci_ok"
printf 'w907_at_interface_14_present=%s\n' "$usb_ok"
# Read-only facts CANNOT establish recovery, backup, auth, app lifecycle,
# per-action consent, modem USSD support, image compatibility or safe flash.
printf 'backup_and_recovery=NOT_VERIFIED\n'
printf 'hardware_uat=NOT_TESTED\n'
printf 'flash_decision=NO_GO\n'
if [ "$board_ok" = 1 ] && [ "$kernel_ok" = 1 ] &&
   [ "$flash_ok" = 1 ] && [ "$os_ok" = 1 ] &&
   [ "$upgrader_ok" = 1 ] && [ "$network_ok" = 1 ] &&
   [ "$wireless_ok" = 1 ] && [ "$luci_ok" = 1 ] &&
   [ "$usb_ok" = 1 ]; then
    printf 'result=READY_FOR_OPERATOR_UAT_ONLY\n'
    exit 0
fi
printf 'result=HARDWARE_EVIDENCE_INCOMPLETE\n'
exit 1
