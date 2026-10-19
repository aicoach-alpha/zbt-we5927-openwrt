#!/bin/sh
# Opt-in XL local logout: add one RPC method, ACL permission and VeCI button.
# Never calls operator endpoints; does not touch LTE, SMS, USSD or LuCI.
set -eu
umask 077
RPC=/usr/libexec/rpcd/veci.xl
ACL=/usr/share/rpcd/acl.d/veci-xl-owner.json
UI=/www/veci/js/lib/veci-xl-connection-status.js
PAGE=/www/veci/js/pages/cellular.js
HELPER=/usr/libexec/veci-xl-session-clear
WORK=/tmp/veci-xl-v6-installer.$$
RPCBAK=/tmp/veci-xl-rpc-before-v6-20261019.sh
ACLBAK=/tmp/veci-xl-acl-before-v6-20261019.json
UIBAK=/tmp/veci-xl-ui-before-v6-20261019.js
fail(){ echo "XL_V6=$1"; exit 1; }
[ ! -e "$WORK" ] && [ ! -L "$WORK" ] || fail temp_conflict
mkdir -m 700 "$WORK" || fail temp_unavailable
trap 'rm -rf "$WORK"' EXIT
[ "$(id -u)" = 0 ] || fail root_required
for file in "$RPC" "$ACL" "$UI" "$PAGE"; do
 [ -f "$file" ] && [ ! -L "$file" ] || fail file_missing
done
[ ! -e "$HELPER" ] && [ ! -L "$HELPER" ] || fail already_installed
[ "$(grep -Fc '"refreshQuota":{}}' "$RPC")" -eq 1 ] || fail rpc_list_anchor_missing
[ "$(grep -Fc 'refreshQuota) refresh_quota ;;' "$RPC")" -eq 1 ] || fail rpc_call_anchor_missing
[ "$(grep -Fxc 'case "$1" in' "$RPC")" -eq 1 ] || fail rpc_case_anchor_missing
[ "$(grep -Fc '"refreshQuota"]' "$ACL")" -eq 1 ] || fail acl_anchor_missing
grep -Fq 'mountXlConnection(root, api)' "$PAGE" || fail ui_anchor_missing
wget -qO "$WORK/clear" https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/da6b3bc27336b7de26cb7c72a37a29de1a5cd7d2/scripts/veci-xl-session-clear-20261019.sh || fail helper_download_failed
wget -qO "$WORK/ui" https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/fc08d6794c8fe36a857d0702727f2c408646891b/web/veci-xl-quota-panel-v6-20261019.js || fail ui_download_failed
sh -n "$WORK/clear" || fail helper_syntax_failed
grep -Fq "api.call('veci.xl','logout'" "$WORK/ui" || fail ui_logout_missing
grep -Fq "q.source!=='operator'" "$WORK/ui" || fail ui_trust_guard_missing
cat > "$WORK/function" <<'EOF'
logout_local() {
 [ "$(id -u)" = 0 ] || fail root_required
 https_only || fail https_only_required
 lock
 [ -x /usr/libexec/veci-xl-session-clear ] || fail logout_helper_missing
 /usr/libexec/veci-xl-session-clear --clear >/dev/null 2>&1 || fail logout_clear_failed
 echo '{"ok":true,"state":"not_connected","scope":"local"}'
}
EOF
awk -v snippet="$WORK/function" '
 $0 == "case \"$1\" in" {
   while ((getline ln < snippet) > 0) print ln
   close(snippet)
 }
 {
   if (index($0,"\"refreshQuota\":{}}") > 0)
     sub(/\"refreshQuota\":\{\}\}/,"\"refreshQuota\":{},\"logout\":{}}")
   print
   if (index($0,"refreshQuota) refresh_quota ;;") > 0)
     print "   logout) logout_local ;;"
 }
' "$RPC" > "$WORK/rpc"
sed 's/"refreshQuota"\]/"refreshQuota", "logout"]/' "$ACL" > "$WORK/acl"
sh -n "$WORK/rpc" || fail rpc_syntax_failed
grep -Fq '"logout":{}' "$WORK/rpc" || fail rpc_list_patch_failed
grep -Fq 'logout) logout_local ;;' "$WORK/rpc" || fail rpc_call_patch_failed
grep -Fq '"logout"]' "$WORK/acl" || fail acl_patch_failed
[ -x /usr/bin/jsonfilter ] && /usr/bin/jsonfilter -i "$WORK/acl" -e '@' >/dev/null || fail acl_json_invalid
cp -p "$RPC" "$RPCBAK" && cp -p "$ACL" "$ACLBAK" && cp -p "$UI" "$UIBAK" || fail backup_failed
rollback(){
 cp "$RPCBAK" "$RPC" && chmod 755 "$RPC" || :
 cp "$ACLBAK" "$ACL" && chmod 644 "$ACL" || :
 cp "$UIBAK" "$UI" && chmod 644 "$UI" || :
 rm -f "$HELPER"
 /etc/init.d/rpcd restart >/dev/null 2>&1 || :
}
if ! {
 cp "$WORK/clear" "$HELPER" && chmod 700 "$HELPER" &&
 cp "$WORK/rpc" "$RPC" && chmod 755 "$RPC" &&
 cp "$WORK/acl" "$ACL" && chmod 644 "$ACL" &&
 cp "$WORK/ui" "$UI" && chmod 644 "$UI" &&
 /etc/init.d/rpcd restart >/dev/null 2>&1
}; then
 rollback
 fail apply_failed_rolled_back
fi
sleep 5
if ! ubus -v list veci.xl 2>/dev/null | grep -Fq '"logout"'; then
 rollback
 fail rpc_integrity_failed_rolled_back
fi
echo XL_V6=installed
echo XL_V6_INTEGRITY=pass
echo XL_V6_LOGOUT=owner_confirmed_local_only
echo XL_V6_BACKUP="$RPCBAK"
