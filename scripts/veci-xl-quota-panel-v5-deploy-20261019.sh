#!/bin/sh
set -eu
TARGET=/www/veci/js/lib/veci-xl-connection-status.js
PAGE=/www/veci/js/pages/cellular.js
TMP=/tmp/veci-xl-v5.$$
BACKUP=/tmp/veci-xl-status-before-v5-20261019.js
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/6a2f00659531112c2260849d65fe3e7a2aa83ae1/web/veci-xl-quota-panel-v5-20261019.js
trap 'rm -f "$TMP"' EXIT
[ -f "$TARGET" ] && [ ! -L "$TARGET" ] || { echo XL_V5=target_missing; exit 1; }
[ -f "$PAGE" ] && grep -Fq 'mountXlConnection(root, api)' "$PAGE" || { echo XL_V5=panel_missing; exit 1; }
wget -qO "$TMP" "$URL" || { echo XL_V5=download_failed; exit 1; }
grep -Fq "cache kedaluwarsa" "$TMP" || { echo XL_V5=invalid_module; exit 1; }
grep -Fq "q.source!=='operator'" "$TMP" || { echo XL_V5=source_guard_missing; exit 1; }
cp -p "$TARGET" "$BACKUP"
cp "$TMP" "$TARGET"
chmod 644 "$TARGET"
echo XL_V5=installed
echo XL_V5_INTEGRITY=pass
echo XL_V5_BACKUP="$BACKUP"
