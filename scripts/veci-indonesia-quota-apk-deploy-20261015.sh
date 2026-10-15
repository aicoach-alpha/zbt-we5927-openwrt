#!/bin/sh
# VeCI Indonesia Quota 0.2.1: targeted signed APK install and rollback.
# For office-laptop-connected ZBT-WE5927, OpenWrt 25.12.5 only.
# No firmware flash/reboot/OTP/modem/SMS commands. May restart rpcd once.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
PKG=veci-telco-indonesia
TAG=veci-indonesia-quota-signed-a0b5b97ff9a2
FILE=veci-telco-indonesia-0.2.1-r1.apk
PKG_HASH=da72b09afefcd2bdf99bc501d86bd8e485f6a7156b8ccdaae189449a3b0ce34f
KEY_HASH=4d1bae271c4cca9b46ac10404d887c246637795f5b89d271fa38672efe9bdbfa
BASE="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$TAG"
LOCK=/tmp/veci-quota-apk-install.lock
WORK=
ATTEMPTED=0
VERIFIED=0
fail() { printf 'VECI_QUOTA_DEPLOY=blocked\nVECI_QUOTA_REASON=%s\n' "$1"; exit 1; }
check_hash() { [ "$(sha256sum "$1" | awk '{print $1}')" = "$2" ]; }
device_gate() {
    [ "$(id -u)" = 0 ] || fail root_required
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_board
    grep -q "^DISTRIB_RELEASE='25.12.5'$" /etc/openwrt_release || fail wrong_os
    for bin in apk wget sha256sum awk mktemp grep wc df ubus jsonfilter tar cp tr; do
        command -v "$bin" >/dev/null 2>&1 || fail required_tool_missing
    done
    free="$(df -k /overlay 2>/dev/null | awk 'NR==2 {print $4}')"
    case "$free" in ''|*[!0-9]*) fail unknown_overlay_free ;; esac
    [ "$free" -ge 256 ] || fail overlay_space_low
}
rollback_internal() {
    # Never uninstall other packages or update the firmware.
    if apk info -e "$PKG" >/dev/null 2>&1; then
        apk --network=false del "$PKG" >/dev/null 2>&1 || return 1
    fi
    if [ "$ATTEMPTED" = 1 ]; then
        /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
    fi
}
finish() {
    rc="$1"
    trap - EXIT INT TERM
    if [ "$ATTEMPTED" = 1 ] && [ "$VERIFIED" = 0 ]; then
        if rollback_internal; then
            printf 'VECI_QUOTA_AUTO_ROLLBACK=pass\n'
        else
            printf 'VECI_QUOTA_AUTO_ROLLBACK=needs_attention\n'
        fi
    fi
    if [ -n "$WORK" ] && [ -d "$WORK" ]; then rm -rf "$WORK"; fi
    rmdir "$LOCK" 2>/dev/null || :
    exit "$rc"
}
[ "$#" -eq 1 ] || fail usage_install_rollback_status
case "$1" in --install|--rollback|--status) mode="$1" ;; *) fail invalid_action ;; esac
device_gate
mkdir "$LOCK" 2>/dev/null || fail lock_exists
trap 'finish $?' EXIT
trap 'exit 130' INT TERM
WORK="$(mktemp -d /tmp/veci-quota-deploy.XXXXXX)" || fail ram_unavailable
mkdir "$WORK/keys"
if [ "$mode" = --status ]; then
    if apk info -e "$PKG" >/dev/null 2>&1; then
        printf 'VECI_QUOTA_PACKAGE=installed\n'
    else
        printf 'VECI_QUOTA_PACKAGE=not_installed\n'
    fi
    if ubus -S call veci.quota status > "$WORK/status.json" 2>/dev/null; then
        state="$(jsonfilter -i "$WORK/status.json" -e '@.state' 2>/dev/null || :)"
        printf 'VECI_QUOTA_RPC_STATE=%s\n' "$state"
    else
        printf 'VECI_QUOTA_RPC_STATE=not_available\n'
    fi
    exit 0
fi
if [ "$mode" = --rollback ]; then
    if ! apk info -e "$PKG" >/dev/null 2>&1; then
        printf 'VECI_QUOTA_ROLLBACK=already_absent\n'
        exit 0
    fi
    [ -x /etc/init.d/rpcd ] || fail rpcd_service_unavailable
    # Explicit rollback only targets the VeCI quota package.
    apk --network=false del "$PKG" > "$WORK/rollback.log" 2>&1 || fail apk_remove_failed
    /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
    [ ! -e /usr/share/luci/menu.d/luci-app-veci-quota.json ] || fail menu_not_removed
    printf 'VECI_QUOTA_ROLLBACK=pass\nVECI_MODEM_AND_SMS_UNCHANGED=true\n'
    exit 0
fi
if apk info -e "$PKG" >/dev/null 2>&1; then fail package_already_installed; fi
for dep in rpcd luci-base jsonfilter; do
    apk info -e "$dep" >/dev/null 2>&1 || fail missing_installed_dependency
done
[ -x /etc/init.d/rpcd ] || fail rpcd_service_unavailable
for path in \
    /usr/libexec/rpcd/veci.quota \
    /usr/libexec/veci-quota-cache \
    /usr/share/veci/telco/providers.json \
    /usr/share/rpcd/acl.d/veci-quota.json \
    /usr/share/luci/menu.d/luci-app-veci-quota.json \
    /www/luci-static/resources/view/veci/quota.js
do
    [ ! -e "$path" ] && [ ! -L "$path" ] || fail existing_path_conflict
done
pkgfile="$WORK/$FILE"
key="$WORK/keys/veci-quota-candidate.pem"
wget -qO "$pkgfile" "$BASE/$FILE" || fail apk_download_failed
wget -qO "$key" "$BASE/veci-quota-candidate.pem" || fail key_download_failed
check_hash "$pkgfile" "$PKG_HASH" || fail apk_hash_invalid
check_hash "$key" "$KEY_HASH" || fail key_hash_invalid
[ "$(wc -c < "$pkgfile" | tr -d '[:space:]')" = 5683 ] || fail apk_size_invalid
[ "$(wc -c < "$key" | tr -d '[:space:]')" = 178 ] || fail key_size_invalid
for src in /etc/apk/keys/*; do
    [ -f "$src" ] && [ ! -L "$src" ] || continue
    cp "$src" "$WORK/keys/" || fail temporary_key_copy_failed
done
apk --keys-dir "$WORK/keys" verify "$pkgfile" > "$WORK/verify.log" 2>&1 ||
    fail apk_signature_rejected
apk --network=false --keys-dir "$WORK/keys" --simulate add "$pkgfile" > "$WORK/plan.log" 2>&1 ||
    fail offline_dependency_plan_failed
if grep -Eiq '(^|[[:space:]])(Upgrading|Downgrading|Purging|Removing)[[:space:]]' "$WORK/plan.log"; then
    fail unintended_package_transaction
fi
tar -cf "$WORK/config-before.tar" -C /etc config 2>/dev/null || fail config_backup_failed
apk list -I > "$WORK/packages-before.txt" 2>/dev/null || fail inventory_backup_failed
printf 'VECI_QUOTA_SIGNATURE=pass\nVECI_QUOTA_DEPENDENCIES=pass\nVECI_QUOTA_VOLATILE_BACKUP=pass\n'
ATTEMPTED=1
# Only intentional persistent change: locally installed quota status APK.
apk --network=false --keys-dir "$WORK/keys" add "$pkgfile" > "$WORK/install.log" 2>&1 ||
    fail apk_install_failed
apk info -e "$PKG" >/dev/null 2>&1 || fail apk_not_registered
for path in \
    /usr/libexec/rpcd/veci.quota \
    /usr/libexec/veci-quota-cache \
    /usr/share/veci/telco/providers.json \
    /usr/share/rpcd/acl.d/veci-quota.json \
    /usr/share/luci/menu.d/luci-app-veci-quota.json \
    /www/luci-static/resources/view/veci/quota.js
do
    [ -f "$path" ] && [ ! -L "$path" ] || fail payload_incomplete
done
# New rpcd plugin may need one reload; SSH connection remains untouched.
if ! ubus -S call veci.quota status > "$WORK/status.json" 2>/dev/null; then
    /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
    ubus -S call veci.quota status > "$WORK/status.json" 2>/dev/null ||
        fail quota_rpc_missing
fi
state="$(jsonfilter -i "$WORK/status.json" -e '@.state' 2>/dev/null || :)"
case "$state" in not_connected|unavailable|stale) : ;; *) fail invalid_quota_state ;; esac
ubus -S call veci.quota providers > "$WORK/providers.json" 2>/dev/null ||
    fail registry_rpc_missing
edition="$(jsonfilter -i "$WORK/providers.json" -e '@.edition' 2>/dev/null || :)"
[ "$edition" = indonesia ] || fail registry_invalid
VERIFIED=1
printf 'VECI_QUOTA_PACKAGE_INSTALL=pass\n'
printf 'VECI_QUOTA_RPC=pass\n'
printf 'VECI_QUOTA_PROVIDER_REGISTRY=pass\n'
printf 'VECI_QUOTA_LOCAL_STATE=%s\n' "$state"
printf 'VECI_QUOTA_ROLLBACK_COMMAND_AVAILABLE=true\n'
printf 'VECI_XL_ACCOUNT_LOGIN=not_attempted\nVECI_OPERATOR_QUOTA=not_verified\n'
printf 'VECI_MODEM_AND_SMS_UNCHANGED=true\n'
