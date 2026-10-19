#!/bin/sh
# Native read-only Data Meter within VeCI Cellular (no changes to SMS/LTE/LuCI).
set -eu
PAGE=/www/veci/js/pages/cellular.js
MODULE=/www/veci/js/lib/cellular-meter-native.js
BASE=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/698ac630ffabb186fe2ffa19eb992acf4abfcc50/web/veci-cellular-meter-native-20261019.js
[ "$(id -u)" = 0 ] || { echo VECI_NATIVE=root_required; exit 1; }
[ -f "$PAGE" ] && [ ! -L "$PAGE" ] && [ -d /www/veci/js/lib ] || { echo VECI_NATIVE=bad_target; exit 1; }
if grep -Fq 'veci-cellular-meter-refresh' "$PAGE"; then echo VECI_NATIVE=already_installed; exit 0; fi
[ "$(grep -Fc 'aria-labelledby="cellular-sms-mifi-title"' "$PAGE")" -eq 1 ] || { echo VECI_NATIVE=unexpected_sms_anchor; exit 1; }
[ "$(grep -Fc "const reconnect = root.querySelector('#cellular-reconnect');" "$PAGE")" -eq 1 ] || { echo VECI_NATIVE=unexpected_render_anchor; exit 1; }
[ ! -e "$MODULE" ] || { echo VECI_NATIVE=module_exists; exit 1; }
temp=/tmp/veci-cellular-native.$$
modtemp=/tmp/veci-meter-module.$$
trap 'rm -f "$temp" "$modtemp"' EXIT
wget -qO "$modtemp" "$BASE" || { echo VECI_NATIVE=download_failed; exit 1; }
grep -Fq 'export async function mountCellularMeter' "$modtemp" || { echo VECI_NATIVE=invalid_module; exit 1; }
awk '
index($0, "<section class=\"panel\" aria-labelledby=\"cellular-sms-mifi-title\">") {
 print "                        <section class=\"panel\" aria-label=\"Data Meter\">"
 print "                          <div class=\"panel-heading\"><div><p class=\"eyebrow\">INTERNET USAGE</p><h3>Data Meter</h3></div></div>"
 print "                          <div id=\"veci-cellular-meter\" role=\"status\">Memuat data modem…</div>"
 print "                          <div class=\"cellular-actions\"><button class=\"button button-secondary\" id=\"veci-cellular-meter-refresh\" type=\"button\">Refresh Data Meter</button></div>"
 print "                          <p>Penghitungan modem bukan saldo resmi operator. Pengaturan patokan manual tersedia di halaman Data Meter.</p>"
 print "                        </section>"
}
index($0,"const reconnect = root.querySelector(") && index($0,"#cellular-reconnect") {
 print "                void import(\"/veci/js/lib/cellular-meter-native.js\").then(m => m.mountCellularMeter(root, api)).catch(() => { const el = root.querySelector(\"#veci-cellular-meter\"); if (el) el.textContent = \"Modul Data Meter tidak tersedia.\"; });"
}
{print}
' "$PAGE" > "$temp"
[ "$(grep -Fc 'id="veci-cellular-meter"' "$temp")" -eq 1 ] || { echo VECI_NATIVE=panel_failed; exit 1; }
[ "$(grep -Fc 'mountCellularMeter(root, api)' "$temp")" -eq 1 ] || { echo VECI_NATIVE=mount_failed; exit 1; }
cp -p "$PAGE" /tmp/veci-cellular-before-native-meter-20261019.js
cp "$modtemp" "$MODULE"
cat "$temp" > "$PAGE"
echo VECI_NATIVE=installed
echo VECI_NATIVE_PAGE=Cellular
echo VECI_NATIVE_BACKUP=/tmp/veci-cellular-before-native-meter-20261019.js
