#!/bin/sh
# Read-only VeCI readiness audit: quota, apps and firmware updating.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
[ "$#" -eq 1 ] && [ "$1" = --status ] || exit 2
echo VECI_PREFLIGHT=read_only
echo ===RPC===
for rpc in veci.quota veci.xl veci.sms veci.ussd; do
 if ubus -S list "$rpc" 2>/dev/null | grep -qx "$rpc"; then echo "$rpc=present"; else echo "$rpc=absent"; fi
done
echo ===XL_STATUS===
ubus -S call veci.xl status 2>/dev/null || echo XL_STATUS=unavailable
ubus -S call veci.quota status 2>/dev/null || echo QUOTA_STATUS=unavailable
echo ===APPS===
for name in veci-app-catalog-we5927 veci-app-guest veci-app-sqm veci-app-ddns veci-app-wireguard veci-app-voucher; do
 if apk list -I 2>/dev/null | grep -q "^${name}-[0-9]"; then echo "$name=installed"; else echo "$name=absent"; fi
done
for key in veci.main.app_feed_enabled veci.main.app_feed_build_id veci.main.app_feed_base_url; do
 value="$(uci -q get "$key" 2>/dev/null || :)"
 [ -n "$value" ] || value=unset
 echo "$key=$value"
done
if [ -f /etc/apk/repositories.d/veci-apps.list ]; then echo APP_REPOSITORY_CONFIG=present; else echo APP_REPOSITORY_CONFIG=absent; fi
echo ===FIRMWARE===
if [ -f /etc/veci-release.json ]; then echo VECI_RELEASE_METADATA=present; else echo VECI_RELEASE_METADATA=absent; fi
if [ -x /sbin/sysupgrade ]; then echo SYSUPGRADE=present; else echo SYSUPGRADE=absent; fi
if command -v fwtool >/dev/null 2>&1; then echo FWTOOL=present; else echo FWTOOL=absent; fi
echo ===RESOURCES===
df -k /overlay 2>/dev/null | tail -n 1 || :
free -k 2>/dev/null | head -n 2 || :
echo VECI_PREFLIGHT_COMPLETE=true
