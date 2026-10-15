#!/bin/sh
# Read-only compatibility evidence for an eventual VeCI-only Cellular quota UI update.
# Never installs, upgrades, edits configuration, queries modem/SMS or exports identity.
set -eu
[ "$#" -eq 1 ] && [ "$1" = --status ] || exit 2
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || {
    echo VECI_QUOTA_UI_BOARD=wrong_device; exit 1;
}
grep -q "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || {
    echo VECI_QUOTA_UI_OPENWRT=wrong_version; exit 1;
}
for bin in apk sha256sum grep awk ubus; do
    command -v "$bin" >/dev/null 2>&1 || { echo VECI_QUOTA_UI_REQUIREMENT=missing; exit 1; }
done
echo VECI_QUOTA_UI_DEVICE=pass
if apk info -e veci >/dev/null 2>&1; then
    echo VECI_QUOTA_UI_CORE_PACKAGE=installed
    apk info -v veci 2>/dev/null | grep '^veci-' | head -1 | sed 's/^/VECI_QUOTA_UI_CORE_VERSION=/' || :
else
    echo VECI_QUOTA_UI_CORE_PACKAGE=not_installed
fi
for name in \
    /www/veci/js/pages/cellular.js \
    /www/veci/js/lib/quota.js
do
    case "$name" in
      */cellular.js) label=CELLULAR ;;
      */quota.js) label=QUOTA_LIB ;;
    esac
    if [ -f "$name" ] && [ ! -L "$name" ]; then
        printf 'VECI_QUOTA_UI_%s_SHA256=' "$label"
        sha256sum "$name" | awk '{print $1}'
    else
        printf 'VECI_QUOTA_UI_%s_SHA256=not_present\n' "$label"
    fi
done
if [ -f /www/veci/js/pages/cellular.js ] && grep -q 'cellular-quota-panel' /www/veci/js/pages/cellular.js; then
    echo VECI_QUOTA_UI_CELLULAR_PANEL_SOURCE=present
else
    echo VECI_QUOTA_UI_CELLULAR_PANEL_SOURCE=not_present
fi
if ubus -S call veci.quota status >/dev/null 2>&1; then
    echo VECI_QUOTA_UI_BACKEND_RPC=pass
else
    echo VECI_QUOTA_UI_BACKEND_RPC=unavailable
fi
echo VECI_QUOTA_UI_PREFLIGHT=read_only
echo VECI_QUOTA_UI_FLASH_WRITES=none
echo VECI_QUOTA_UI_SMS_MODEM_UNTOUCHED=true
