#!/bin/sh
# Guarded XL readiness panel integration in VeCI Cellular only.
set -eu
PAGE=/www/veci/js/pages/cellular.js
MOD=/www/veci/js/lib/veci-xl-connection-status.js
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/65fd99f5de475a830542a7650a71810117162a96/web/veci-xl-connection-status-20261019.js
[ -f "$PAGE" ] && [ ! -L "$PAGE" ] || { echo XL_UI=page_missing; exit 1; }
if grep -Fq 'id="veci-xl-connection"' "$PAGE"; then echo XL_UI=already_installed; exit 0; fi
[ "$(grep -Fc 'id="veci-cellular-meter-refresh"' "$PAGE")" -eq 1 ] || { echo XL_UI=anchor_missing; exit 1; }
[ "$(grep -Fc 'const reconnect = root.querySelector(' "$PAGE")" -eq 1 ] || { echo XL_UI=render_anchor_missing; exit 1; }
[ ! -e "$MOD" ] || { echo XL_UI=module_conflict; exit 1; }
TMP=/tmp/veci-xl-ui.$$
MTMP=/tmp/veci-xl-ui-module.$$
trap 'rm -f "$TMP" "$MTMP"' EXIT
wget -qO "$MTMP" "$URL" || { echo XL_UI=download_failed; exit 1; }
grep -Fq 'export async function mountXlConnection' "$MTMP" || { echo XL_UI=invalid_module; exit 1; }
awk '
index($0, "<section class=\"panel\" aria-labelledby=\"cellular-sms-mifi-title\">") {
print "                    <section class=\"panel\" aria-label=\"XL account connection\">"
print "                      <div class=\"panel-heading\"><div><p class=\"eyebrow\">XL ACCOUNT</p><h3>Koneksi myXL</h3></div></div>"
print "                      <div id=\"veci-xl-connection\" role=\"status\">Memeriksa konfigurasi XL…</div>"
print "                    </section>"
}
index($0,"const reconnect = root.querySelector(") {
print "                void import(\"/veci/js/lib/veci-xl-connection-status.js\").then(m => m.mountXlConnection(root, api)).catch(() => { const el = root.querySelector(\"#veci-xl-connection\"); if (el) el.textContent = \"Status XL tidak tersedia.\"; });"
}
{print}
' "$PAGE" > "$TMP"
[ "$(grep -Fc 'id="veci-xl-connection"' "$TMP")" -eq 1 ] || { echo XL_UI=template_failed; exit 1; }
[ "$(grep -Fc 'mountXlConnection(root, api)' "$TMP")" -eq 1 ] || { echo XL_UI=init_failed; exit 1; }
cp -p "$PAGE" /tmp/veci-cellular-before-xl-status-20261019.js
cp "$MTMP" "$MOD"
cat "$TMP" > "$PAGE"
echo XL_UI=installed
echo XL_UI_BACKUP=/tmp/veci-cellular-before-xl-status-20261019.js
