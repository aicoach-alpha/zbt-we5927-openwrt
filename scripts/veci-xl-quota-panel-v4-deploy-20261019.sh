#!/bin/sh
set -eu
TARGET=/www/veci/js/lib/veci-xl-connection-status.js
PAGE=/www/veci/js/pages/cellular.js
TMP=/tmp/veci-xl-v4.$$
BACKUP=/tmp/veci-xl-status-before-v4-20261019.js
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/0431bfb5fb4e1250af4c4c6c01bcdf3f0b397ffb/web/veci-xl-quota-panel-v4-20261019.js
trap 'rm -f "$TMP"' EXIT
[ -f "$TARGET" ] && [ ! -L "$TARGET" ] || { echo XL_V4=target_missing; exit 1; }
[ -f "$PAGE" ] && grep -Fq 'mountXlConnection(root, api)' "$PAGE" || { echo XL_V4=panel_missing; exit 1; }
wget -qO "$TMP" "$URL" || { echo XL_V4=download_failed; exit 1; }
grep -Fq "q.provider!=='xl'" "$TMP" || { echo XL_V4=contract_missing; exit 1; }
grep -Fq "q.source!=='operator'" "$TMP" || { echo XL_V4=trust_guard_missing; exit 1; }
cp -p "$TARGET" "$BACKUP"
cp "$TMP" "$TARGET"
chmod 644 "$TARGET"
echo XL_V4=installed
echo XL_V4_CONTRACT=provider_or_operator
echo XL_V4_SOURCE_GUARD=present
echo XL_V4_BACKUP="$BACKUP"
