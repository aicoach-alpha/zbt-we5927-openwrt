#!/bin/sh
# Remove VeCI USSD only. Preserve modem LTE, SMS/OTP and XL operator API.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
MODE="$1"
BACK=/tmp/veci-ussd-removal-20261016
UI=/www/veci/js/pages/cellular.js
fail(){ echo "VECI_USSD_REMOVAL=blocked"; echo "VECI_USSD_REASON=$1"; exit 1; }
case "$MODE" in --verify|--apply|--status) ;; *) fail usage;; esac
[ "$(id -u)" -eq 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = 'zbtlink,zbt-we5927' ] || fail wrong_board
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
for tool in awk apk basename cp chmod grep mkdir mv rm sha256sum ubus; do command -v "$tool" >/dev/null 2>&1 || fail missing_tool; done
ussd_files(){
 for p in \
  /usr/libexec/rpcd/veci.ussd \
  /usr/libexec/veci-xl-ussd \
  /usr/libexec/veci-xl-ussd-once \
  /usr/libexec/veci-xl-quota-cache \
  /usr/share/rpcd/acl.d/veci-ussd-acl.json \
  /usr/share/rpcd/acl.d/veci-ussd.json \
  /usr/share/rpcd/acl.d/veci-xl-ussd.json \
  /www/veci/xl-ussd-guide.html \
  /www/veci/xl-ussd-guide.js; do
  [ ! -e "$p" ] && [ ! -L "$p" ] || printf '%s\n' "$p"
 done
}
pkg(){ apk list -I 2>/dev/null | grep -q '^veci-ussd-dialer-[0-9]'; }
status(){
 if ubus -S list veci.ussd 2>/dev/null | grep -qx veci.ussd; then echo VECI_USSD_RPC=present; else echo VECI_USSD_RPC=absent; fi
 if pkg; then echo VECI_USSD_PACKAGE=installed; else echo VECI_USSD_PACKAGE=absent; fi
 if [ -f "$UI" ] && grep -q 'id="cellular-xl-ussd"' "$UI"; then echo VECI_USSD_UI=present; else echo VECI_USSD_UI=absent; fi
 echo "VECI_USSD_FILES_PRESENT=$(ussd_files | wc -l | tr -d '[:space:]')"
 if ubus -S list veci.sms 2>/dev/null | grep -qx veci.sms; then echo VECI_SMS_RPC=present; else echo VECI_SMS_RPC=missing; fi
 if ubus -S list veci.quota 2>/dev/null | grep -qx veci.quota; then echo VECI_QUOTA_RPC=present; else echo VECI_QUOTA_RPC=missing; fi
}
[ "$MODE" = --status ] && { status; exit 0; }
[ -f "$UI" ] && [ ! -L "$UI" ] || fail core_ui_missing
[ -x /usr/libexec/rpcd/veci.sms ] || fail sms_missing
[ -x /usr/libexec/rpcd/veci.quota ] || fail quota_missing
[ -x /usr/libexec/rpcd/veci.xl ] || fail xl_api_missing
[ -x /usr/sbin/we5927-lte ] || fail lte_missing
if grep -q 'id="cellular-xl-ussd"' "$UI"; then
 for marker in 'function parseXlUssdQuota(text) {' '<section class="notice-card" id="cellular-xl-ussd">' '// XL USSD is a separate write-ACL feature' "const reconnect = root.querySelector('#cellular-reconnect');"; do
  [ "$(grep -F -c "$marker" "$UI" || :)" -eq 1 ] || fail ui_marker_mismatch
 done
else
 ! grep -q 'veci.ussd' "$UI" || fail unexpected_ui
fi
[ ! -L "$BACK" ] && [ ! -e "$BACK" ] || fail previous_backup_present
if [ "$MODE" = --verify ]; then
 echo VECI_USSD_PREFLIGHT=pass
 echo VECI_USSD_REMOVAL=not_applied
 status
 exit 0
fi
mkdir -m 700 "$BACK" || fail backup_failed
mkdir -m 700 "$BACK/files"
cp -p "$UI" "$BACK/cellular.js" || fail ui_backup_failed
ussd_files | while IFS= read -r p; do
 [ -f "$p" ] && [ ! -L "$p" ] || exit 1
 cp -p "$p" "$BACK/files/$(basename "$p")" || exit 1
done
if grep -q 'id="cellular-xl-ussd"' "$UI"; then
 awk '
  index($0,"function parseXlUssdQuota(text) {") {helper++;block=1;next}
  block==1 {if($0=="}") block=0;next}
  index($0,"<section class=\"notice-card\" id=\"cellular-xl-ussd\">") {section++;block=2;next}
  block==2 {if(index($0,"</section>")) block=0;next}
  index($0,"// XL USSD is a separate write-ACL feature") {handler++;block=3;next}
  block==3 {if(index($0,"const reconnect = root.querySelector")){block=0;print};next}
  {print}
  END {if(block!=0 || helper!=1 || section!=1 || handler!=1) exit 42}
 ' "$UI" > "$BACK/cellular-clean.js" || fail ui_transform_failed
 [ -s "$BACK/cellular-clean.js" ] || fail ui_empty
 ! grep -q 'veci.ussd' "$BACK/cellular-clean.js" || fail ui_reference_remaining
 cp "$BACK/cellular-clean.js" "$UI.veci-no-ussd.$$" || fail ui_stage_failed
 chmod 644 "$UI.veci-no-ussd.$$"
 mv -f "$UI.veci-no-ussd.$$" "$UI" || fail ui_commit_failed
fi
# Only exact VeCI USSD file paths; no modem AT, SMS or API quota files.
ussd_files | while IFS= read -r p; do rm -f "$p" || exit 1; done
if pkg; then apk del veci-ussd-dialer || fail package_removal_failed; fi
rm -f /tmp/veci-xl-ussd.session
/etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
[ ! -e /usr/libexec/rpcd/veci.ussd ] || fail rpc_file_remaining
if ubus -S list veci.ussd 2>/dev/null | grep -qx veci.ussd; then fail rpc_still_registered; fi
ubus -S list veci.sms | grep -qx veci.sms || fail sms_lost
ubus -S list veci.quota | grep -qx veci.quota || fail quota_lost
[ -x /usr/libexec/rpcd/veci.xl ] || fail xl_api_lost
! pkg || fail package_remained
echo VECI_USSD_REMOVAL=pass
echo VECI_USSD_MODEM_CHANGED=false
echo VECI_SMS_PRESERVED=true
echo VECI_XL_API_PRESERVED=true
status
