#!/bin/sh
# VeCI-only XL Native 0.3.6 — pinned signed APK, no Core or modem changes.
# Use only on the OWNER's actual WE5927 from the Windows office laptop.
# Modes: --status (read-only), --verify (read-only), --install, --rollback.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
TAG=veci-xl-native-036-5cfa0e0d3860
BASE="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$TAG"
APK=veci-telco-xl-native-0.3.6-r1.apk
KEY=veci-xl-036.pem
APK_SHA=ca670e83b5dc454b8d0afd736846e55e578d8c0aad67ada5112b3273f2eee82c
KEY_SHA=2301eb6954b58d29bd9f76a1616a9182fc5efb04d70c29b7b6e2d4db83cfb48e
CORE_CELL_SHA=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
CORE_QUOTA_SHA=5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d
CORE_RPCD_SHA=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
CORE_ACL_SHA=d655406fd94214c22cf047bf5fc49e66876365634958be9d25171e6100e6a171
CORE_CONFIG_SHA=95927da8bad40be6ac0eb14d8c92d13fa82ffc1594a8f608d59a06680275caae
LOCK=/tmp/veci-xl-036-install.lock
WORK=
APPLIED=0
COMPLETE=0
KEEP=0
fail(){ printf 'VECI_XL_036_INSTALL=blocked\nVECI_XL_036_REASON=%s\n' "$1"; exit 1; }
hash(){ sha256sum "$1" | awk '{print $1}'; }
check(){ [ -f "$1" ] && [ ! -L "$1" ] && [ "$(hash "$1")" = "$2" ]; }
installed(){
 apk list -I 2>/dev/null | grep -q "^$1-"
}
safe_dir(){
 [ -d "$1" ] && [ ! -L "$1" ] &&
 [ "$(ls -ldn "$1" | awk '{print $1 " " $3}')" = "drwx------ $(id -u)" ]
}
safe_file(){
 [ -f "$1" ] && [ ! -L "$1" ] &&
 [ "$(ls -ldn "$1" | awk '{print $1 " " $3}')" = "-rw------- $(id -u)" ]
}
https_ready(){
 [ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] &&
 [ -n "$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)" ] || return 1
 cert="$(uci -q get uhttpd.main.cert 2>/dev/null || :)"
 key="$(uci -q get uhttpd.main.key 2>/dev/null || :)"
 [ -n "$cert" ] && [ -f "$cert" ] &&
 [ -n "$key" ] && [ -f "$key" ]
}
operator_ready(){
 safe_dir /tmp/veci-xl-ciam &&
 safe_dir /tmp/veci-telco-private || return 1
 for name in basic_auth user_agent fingerprint device_id ax_api_sig_key; do
  safe_file "/tmp/veci-xl-ciam/$name" || return 1
 done
 for name in xdata_key api_key signature_secret; do
  safe_file "/tmp/veci-telco-private/$name" || return 1
 done
}
readiness(){
 if https_ready; then echo VECI_XL_036_ROUTER_HTTPS_ONLY=pass
 else echo VECI_XL_036_ROUTER_HTTPS_ONLY=blocked; fi
 if operator_ready; then echo VECI_XL_036_OPERATOR_CREDENTIALS=configured
 else echo VECI_XL_036_OPERATOR_CREDENTIALS=not_configured; fi
}
core_guard(){
 installed 'veci-0.2.2' || fail veci_core_version_changed
 check /www/veci/js/pages/cellular.js "$CORE_CELL_SHA" || fail core_cellular_changed
 check /www/veci/js/lib/native-quota.js "$CORE_QUOTA_SHA" || fail core_quota_changed
 check /usr/libexec/rpcd/veci "$CORE_RPCD_SHA" || fail core_rpcd_changed
 check /usr/share/rpcd/acl.d/veci.json "$CORE_ACL_SHA" || fail core_acl_changed
 check /etc/config/veci "$CORE_CONFIG_SHA" || fail core_private_config_changed
 ubus -S call veci.quota status >/dev/null 2>&1 || fail quota_status_unavailable
 ubus -S call veci.cellular status >/dev/null 2>&1 || fail cellular_status_unavailable
}
target_guard(){
 for p in /usr/libexec/rpcd/veci.xl \
   /usr/share/rpcd/acl.d/veci-xl-owner.json \
   /www/veci/xl-account.html /www/veci/xl-account.js; do
  [ -f "$p" ] && [ ! -L "$p" ] || fail xl_plugin_file_missing
 done
 sh -n /usr/libexec/rpcd/veci.xl || fail xl_rpc_syntax_error
 ubus -S list veci.xl 2>/dev/null | grep -qx 'veci.xl' || fail xl_rpc_not_registered
 ubus -S call veci.xl status >/dev/null 2>&1 || fail xl_status_failed
}
restore(){
 apk --no-network del veci-telco-xl-native >/dev/null 2>&1 || return 1
 /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
 if installed veci-telco-xl-native; then return 1; fi
 core_guard
 echo VECI_XL_036_ROLLBACK=pass
}
finish(){
 code="$1"
 trap - EXIT INT TERM
 if [ "$APPLIED" = 1 ] && [ "$COMPLETE" = 0 ]; then
  restore || { KEEP=1; echo VECI_XL_036_ROLLBACK=needs_attention; }
 fi
 if [ "$KEEP" = 0 ] && [ -n "$WORK" ] && [ -d "$WORK" ]; then
  rm -rf "$WORK"
 fi
 rmdir "$LOCK" 2>/dev/null || :
 exit "$code"
}
[ "$#" = 1 ] || fail usage
case "$1" in --status|--verify|--install|--rollback) MODE="$1" ;; *) fail usage ;; esac
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = 'zbtlink,zbt-we5927' ] || fail wrong_router
grep -q "^DISTRIB_RELEASE='25.12.5'$" /etc/openwrt_release || fail firmware_mismatch

if [ "$MODE" = --status ]; then
 if installed veci-telco-xl-native; then
  echo VECI_XL_036_PACKAGE=installed
 else
  echo VECI_XL_036_PACKAGE=not_installed
 fi
 if ubus -S list veci.xl 2>/dev/null | grep -qx 'veci.xl'; then
  echo VECI_XL_036_RPC=registered
  ubus -S call veci.xl status || :
 else echo VECI_XL_036_RPC=not_registered; fi
 readiness
 echo VECI_XL_036_MODEM_SMS_UNCHANGED=true
 exit 0
fi

mkdir "$LOCK" 2>/dev/null || fail operation_in_progress
trap 'finish $?' EXIT
trap 'exit 130' INT TERM
core_guard

if [ "$MODE" = --rollback ]; then
 installed veci-telco-xl-native || fail xl_native_not_installed
 restore || fail rollback_failed
 COMPLETE=1
 exit 0
fi
if installed veci-telco-xl-native; then
 target_guard
 echo VECI_XL_036_INSTALL=already_installed
 COMPLETE=1
 exit 0
fi
for p in /usr/libexec/rpcd/veci.xl \
 /usr/share/rpcd/acl.d/veci-xl-owner.json \
 /www/veci/xl-account.html /www/veci/xl-account.js; do
 [ ! -e "$p" ] && [ ! -L "$p" ] || fail existing_unowned_xl_file
done
free="$(df -k /overlay | awk 'NR==2 {print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_unknown ;; esac
[ "$free" -ge 640 ] || fail overlay_too_full

WORK="$(mktemp -d /tmp/veci-xl036.XXXXXX)" || fail ram_unavailable
mkdir "$WORK/keys" || fail trust_temp_failed
for file in "$APK" "$KEY"; do
 wget -qO "$WORK/$file" "$BASE/$file" || fail signed_asset_download_failed
done
check "$WORK/$APK" "$APK_SHA" || fail apk_integrity_failed
check "$WORK/$KEY" "$KEY_SHA" || fail key_integrity_failed
[ "$(wc -c < "$WORK/$APK" | tr -d '[:space:]')" = 34460 ] || fail apk_size_wrong
for key in /etc/apk/keys/*; do
 [ -f "$key" ] && [ ! -L "$key" ] || continue
 cp "$key" "$WORK/keys/" || fail key_copy_failed
done
cp "$WORK/$KEY" "$WORK/keys/$KEY" || fail new_public_key_failed
apk --keys-dir "$WORK/keys" verify "$WORK/$APK" >/dev/null 2>&1 ||
 fail signed_apk_rejected
apk --no-network --keys-dir "$WORK/keys" --simulate add "$WORK/$APK" > "$WORK/plan.log" 2>&1 ||
 fail transaction_simulation_failed
if grep -Ei '(^|[[:space:]])(Installing|Removing|Purging|Upgrading|Downgrading)[[:space:]]' "$WORK/plan.log" |
 grep -Ev '(^|[[:space:]])veci-telco-xl-native([ -]|$)' >/dev/null 2>&1; then
 fail unrelated_package_transaction
fi
echo VECI_XL_036_SIGNED_PREFLIGHT=pass
readiness
if [ "$MODE" = --verify ]; then
 echo VECI_XL_036_PACKAGE_INSTALLED=false
 echo VECI_XL_036_SERVICES_RESTARTED=false
 echo VECI_XL_036_MODEM_SMS_UNCHANGED=true
 COMPLETE=1
 exit 0
fi
https_ready || fail https_only_configuration_required
operator_ready || fail authorized_operator_configuration_missing
apk list -I > "$WORK/before.list"
grep -v '^veci-telco-xl-native-' "$WORK/before.list" | sort > "$WORK/before.others"
APPLIED=1
apk --no-network --keys-dir "$WORK/keys" add "$WORK/$APK" > "$WORK/install.log" 2>&1 ||
 fail package_install_failed
installed 'veci-telco-xl-native-0.3.6' || fail wrong_installed_version
/etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_reload_failed
target_guard
core_guard
apk list -I > "$WORK/after.list"
grep -v '^veci-telco-xl-native-' "$WORK/after.list" | sort > "$WORK/after.others"
cmp -s "$WORK/before.others" "$WORK/after.others" ||
 fail other_packages_changed
COMPLETE=1
echo VECI_XL_036_INSTALL=pass
echo VECI_XL_036_HTTPS_POLICY=enforced
echo VECI_XL_036_CORE_022_PRESERVED=pass
echo VECI_XL_036_ROLLBACK=available
echo VECI_XL_036_ACCOUNT_UAT=pending
echo VECI_XL_036_LUCI_MODIFIED=false
echo VECI_XL_036_MODEM_SMS_UNCHANGED=true
