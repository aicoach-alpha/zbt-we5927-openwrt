#!/bin/sh
set -eu
TARGET=/www/veci/js/lib/veci-xl-connection-status.js
PAGE=/www/veci/js/pages/cellular.js
TMP=/tmp/veci-xl-quota-v3.$$
BACKUP=/tmp/veci-xl-status-before-v3-20261019.js
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/7e48579ee8fdace3f3f2739bcb5c21b01d4fd085/web/veci-xl-quota-panel-v3-20261019.js
trap 'rm -f "$TMP"' EXIT
[ -f "$TARGET" ] && [ ! -L "$TARGET" ] || { echo XL_V3=module_missing; exit 1; }
[ -f "$PAGE" ] && grep -Fq 'mountXlConnection(root, api)' "$PAGE" || { echo XL_V3=anchor_missing; exit 1; }
wget -qO "$TMP" "$URL" || { echo XL_V3=download_failed; exit 1; }
grep -Fq "api.call('veci.quota','status'" "$TMP" || { echo XL_V3=invalid_module; exit 1; }
cp -p "$TARGET" "$BACKUP"
cp "$TMP" "$TARGET"
chmod 644 "$TARGET"
echo XL_V3=installed
echo XL_V3_BACKUP="$BACKUP"
echo XL_V3_INTEGRITY="$(grep -c 'veci.quota' "$TARGET")"
