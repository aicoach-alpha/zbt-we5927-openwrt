#!/bin/sh
# VeCI integration preflight: operator API, optional apps, manual/OTA firmware.
# Read-only. No modem AT, USSD, SMS content, apk modifications or flash.
set -eu
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
[ "$#" -eq 1 ] && [ "$1" = --status ] || { echo VECI_PREFLIGHT=invalid_mode; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo VECI_PREFLIGHT=root_required; exit 1; }
rpc(){ ubus -S list "$1" 2>/dev/null | grep -qx "$1"; }
echo VECI_PREFLIGHT=read_only
if [ -r /tmp/sysinfo/board_name ]; then
  case "$(cat /tmp/sysinfo/board_name)" in
   zbtlink,zbt-we5927) echo VECI_BOARD=WE5927 ;;
   *) echo VECI_BOARD=unexpected ;;
  esac
else echo VECI_BOARD=unknown; fi
for obj in veci veci.cellular veci.quota veci.xl veci.sms veci.ussd veci.apps veci.firmware rpc-sys; do
 if rpc "$obj"; then printf 'VECI_RPC_%s=present\n' "$obj"; else printf 'VECI_RPC_%s=absent\n' "$obj"; fi
done
echo VECI_XL_ACCOUNT_STATUS_BEGIN
if rpc veci.xl; then
 ubus -S call veci.xl status 2>/dev/null || echo VECI_XL_STATUS=error
else echo VECI_XL_STATUS=rpc_missing; fi
echo VECI_XL_ACCOUNT_STATUS_END
echo VECI_OPERATOR_QUOTA_BEGIN
if rpc veci.quota; then
 ubus -S call veci.quota status 2>/dev/null || echo VECI_OPERATOR_QUOTA=error
else echo VECI_OPERATOR_QUOTA=rpc_missing; fi
echo VECI_OPERATOR_QUOTA_END
echo VECI_RPC_CORE_METHODS_BEGIN
if [ -x /usr/libexec/rpcd/veci ]; then /usr/libexec/rpcd/veci list 2>/dev/null || :; else echo VECI_RPC_CORE_METHODS=unavailable; fi
echo VECI_RPC_CORE_METHODS_END
echo VECI_APP_PACKAGES_BEGIN
apk list -I 2>/dev/null | grep -E '^(veci|ddns-scripts|sqm-scripts|wireguard-tools|uspot|opennds)-' | sed -n '1,60p' || :
echo VECI_APP_PACKAGES_END
for app in guest sqm ddns wireguard voucher; do
 if [ -f "/usr/share/veci/apps/$app.json" ]; then printf 'VECI_APP_CATALOG_%s=present\n' "$app"; else printf 'VECI_APP_CATALOG_%s=absent\n' "$app"; fi
done
if [ -f /etc/apk/repositories.d/veci-apps.list ]; then echo VECI_APP_REPO=present; else echo VECI_APP_REPO=absent; fi
if [ "$(uci -q get veci.main.app_feed_enabled 2>/dev/null || :)" = 1 ]; then echo VECI_APP_FEED=enabled; else echo VECI_APP_FEED=disabled; fi
if [ -x /usr/sbin/veci-update-agent ]; then echo VECI_UPDATE_AGENT=installed; else echo VECI_UPDATE_AGENT=absent; fi
if [ -r /etc/veci-release.json ]; then echo VECI_RELEASE_METADATA=present; else echo VECI_RELEASE_METADATA=absent; fi
if [ -x /sbin/sysupgrade ]; then echo VECI_SYSUPGRADE_BINARY=present; else echo VECI_SYSUPGRADE_BINARY=absent; fi
if [ -e /www/veci/js/pages/system.js ]; then echo VECI_SYSTEM_UI=present; else echo VECI_SYSTEM_UI=absent; fi
if [ -e /www/veci/js/pages/apps.js ]; then echo VECI_APPS_UI=present; else echo VECI_APPS_UI=absent; fi
echo VECI_OVERLAY_BEGIN
df -k /overlay 2>/dev/null | sed -n '1,3p' || :
echo VECI_OVERLAY_END
echo VECI_MEMORY_BEGIN
grep -E '^Mem(Total|Available):' /proc/meminfo 2>/dev/null || :
echo VECI_MEMORY_END
echo VECI_LIVE_ASSET_SHA256_BEGIN
for f in /www/veci/index.html /www/veci/js/pages/cellular.js /www/veci/js/pages/apps.js /www/veci/js/pages/system.js /usr/libexec/rpcd/veci; do
 if [ -f "$f" ] && [ ! -L "$f" ]; then sha256sum "$f"; else echo "$f unavailable"; fi
done
echo VECI_LIVE_ASSET_SHA256_END
echo VECI_PREFLIGHT_MODEM_CHANGED=false
echo VECI_PREFLIGHT_PACKAGES_CHANGED=false
echo VECI_PREFLIGHT_OTA_FLASHED=false
