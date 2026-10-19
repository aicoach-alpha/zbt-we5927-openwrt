#!/bin/sh
# Upgrade only the XL readiness UI module, preserve router services.
set -eu
TARGET=/www/veci/js/lib/veci-xl-connection-status.js
PAGE=/www/veci/js/pages/cellular.js
BACKUP=/tmp/veci-xl-status-before-v2-20261019.js
TMP=/tmp/veci-xl-status-v2.$$
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/61c9fca68863d3a6a9b87282197f2fb053962ec9/web/veci-xl-connection-status-v2-20261019.js
trap 'rm -f "$TMP"' EXIT
[ -f "$TARGET" ] && [ ! -L "$TARGET" ] || { echo XL_V2=module_missing; exit 1; }
[ -f "$PAGE" ] && grep -Fq 'mountXlConnection(root, api)' "$PAGE" || { echo XL_V2=panel_missing; exit 1; }
wget -qO "$TMP" "$URL" || { echo XL_V2=download_failed; exit 1; }
grep -Fq 'export async function mountXlConnection' "$TMP" || { echo XL_V2=invalid_module; exit 1; }
grep -Fq 'Refresh Status XL' "$TMP" || { echo XL_V2=missing_refresh; exit 1; }
cp -p "$TARGET" "$BACKUP"
cp "$TMP" "$TARGET"
chmod 644 "$TARGET"
echo XL_V2=installed
echo XL_V2_BACKUP="$BACKUP"
