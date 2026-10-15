#!/bin/sh
# VeCI Indonesia quota LuCI 0.2.1 — physical APK trust/compatibility PREFLIGHT.
# Scope: WE5927 running OpenWrt 25.12.5. NO installation or firmware changes.
# The router is reachable ONLY through the owner's office Windows laptop.
# This script uses volatile /tmp exclusively and does not touch modem or SMS.
set -eu
umask 077
LC_ALL=C
export LC_ALL
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

fail() {
    printf 'VECI_INDONESIA_APK_PREFLIGHT=blocked\n'
    printf 'VECI_INDONESIA_APK_REASON=%s\n' "$1"
    printf 'VECI_INDONESIA_APK_INSTALLED=false\n'
    exit 1
}
[ "$#" -eq 1 ] && [ "$1" = "--verify" ] || fail usage

board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
[ "$board" = "zbtlink,zbt-we5927" ] || fail wrong_device

release="$(sed -n "s/^DISTRIB_RELEASE=['\"]\{0,1\}\\([^'\"]*\\).*$/\\1/p" /etc/openwrt_release 2>/dev/null | head -n 1)"
[ "$release" = "25.12.5" ] || fail different_openwrt_release

for tool in apk wget sha256sum awk mktemp wc df; do
    command -v "$tool" >/dev/null 2>&1 || fail missing_tool
done
[ -d /overlay ] || fail overlay_unavailable

free_kib="$(df -k /overlay 2>/dev/null | awk 'NR==2 {print $4}')"
case "$free_kib" in ''|*[!0-9]*) fail overlay_unknown ;; esac
[ "$free_kib" -ge 256 ] || fail overlay_low_space

# Read-only device capability check; no user credentials or phone metadata.
[ -x /usr/sbin/rpcd ] || [ -x /sbin/rpcd ] || fail rpcd_unavailable
[ -d /www/luci-static/resources ] || fail luci_unavailable

work="$(mktemp -d /tmp/veci-indonesia-quota-apk.XXXXXX)" || fail ram_unavailable
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT TERM

tag=veci-indonesia-quota-apk-fb9630bdc1cd
file=veci-telco-indonesia-0.2.1-r1.apk
expected=7ebb290ff5973c52a970f2e78b784254dcbafc3e5256633affaad9644685f8b4
url="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$tag/$file"
wget -qO "$work/$file" "$url" || fail package_download_failed
got="$(sha256sum "$work/$file" | awk '{print $1}')"
[ "$got" = "$expected" ] || fail package_sha256_invalid
n="$(wc -c < "$work/$file" | tr -d '[:space:]')"
[ "$n" = 5567 ] || fail package_size_invalid

printf 'VECI_INDONESIA_APK_BOARD=pass\n'
printf 'VECI_INDONESIA_APK_OPENWRT_VERSION=pass\n'
printf 'VECI_INDONESIA_APK_OVERLAY_SPACE=pass\n'
printf 'VECI_INDONESIA_APK_SHA256=pass\n'

# OpenWrt apk --simulate is read-only. Signature and dependency gate MUST
# pass without --allow-untrusted or any modification of /etc/apk/keys.
if apk --simulate add "$work/$file" > "$work/apk-simulated.txt" 2>&1; then
    printf 'VECI_INDONESIA_APK_TRUST_AND_DEPENDENCIES=pass\n'
else
    printf 'VECI_INDONESIA_APK_TRUST_AND_DEPENDENCIES=blocked\n'
    printf 'VECI_INDONESIA_APK_REASON=signature_or_dependency_not_verified\n'
    printf 'VECI_INDONESIA_APK_INSTALLED=false\n'
    exit 3
fi
printf 'VECI_INDONESIA_APK_PREFLIGHT=pass\n'
printf 'VECI_INDONESIA_APK_INSTALLED=false\n'
printf 'VECI_XL_ACCOUNT_LOGIN=not_attempted\n'
printf 'VECI_OPERATOR_QUOTA=not_verified\n'
printf 'VECI_MODEM_AND_SMS_UNCHANGED=true\n'
printf 'VECI_FLASH_WRITES=none\n'
