#!/bin/sh
# WE5927 VeCI 0.2.2: safe read-only package transaction preflight.
# NEVER installs packages or touches modem/SMS/network; office laptop only.
# Paired release APK hashes are GitHub-release-proven and P-256 signatures
# are verified using a temporary trust directory (never system trust).
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH

TAG=veci-physical-core-022-b9f91e84899c
BASE="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$TAG"
NEW=veci-0.2.2-r1.apk
OLD=veci-0.2.0-r1.apk
KEY=veci-physical-022.pem
NEW_SHA=57e1c66473e9ce4d7fb920beaeb82dadabfbf7d6984f52837b826d11cb1f1793
OLD_SHA=b30d66c259d3a90ffafabecbe0a36baa9377af76e9f51341c1b0c13078c8f1c7
KEY_SHA=2d27345b4b48c70131ea03799af96699625378a571dfa1d67c2f18f40ded4147
LIVE_PAGE=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
LIVE_MODULE=5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d
LIVE_CSS=fd3b3540109d815d9b3cb5151298af04ef865e55557d8a8a91d9c30f1548fdb2
EXPECTED_RPCD=2b83fac1da487188617888757a2b769d6ed9bf94d32aeaa9a87139b008f913da
EXPECTED_ACL=1c59a295448483147507d58336a554db96803aebf4eff8263bc73e89ace6eb5b
WORK=
fail() {
    echo VECI_022_PREFLIGHT=blocked
    printf 'VECI_022_REASON=%s\n' "$1"
    exit 1
}
sha() { sha256sum "$1" | awk '{print $1}'; }
check() { [ -f "$1" ] && [ ! -L "$1" ] && [ "$(sha "$1")" = "$2" ]; }
[ "$#" -eq 1 ] && [ "$1" = --verify ] || fail usage
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_device
grep -q "^DISTRIB_RELEASE='25.12.5'$" /etc/openwrt_release || fail wrong_openwrt_release
for bin in apk wget sha256sum awk grep df wc mktemp mkdir cp ubus; do
    command -v "$bin" >/dev/null 2>&1 || fail missing_system_tool
done
apk list -I 2>/dev/null | grep -q '^veci-0[.]2[.]0-r1' || fail core_version_not_0_2_0
check /www/veci/js/pages/cellular.js "$LIVE_PAGE" || fail active_cellular_source_drift
check /www/veci/js/lib/native-quota.js "$LIVE_MODULE" || fail active_quota_module_drift
check /www/veci/sms-center.css "$LIVE_CSS" || fail sms_ui_css_drift
check /usr/libexec/rpcd/veci "$EXPECTED_RPCD" || fail existing_core_rpcd_drift
check /usr/share/rpcd/acl.d/veci.json "$EXPECTED_ACL" || fail existing_core_acl_drift
ubus -S call veci.quota status >/dev/null 2>&1 || fail backend_quota_unavailable
ubus -S call veci.cellular status >/dev/null 2>&1 || fail backend_cellular_unavailable
free="$(df -k /overlay | awk 'NR==2 {print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_space_unreadable ;; esac
[ "$free" -ge 768 ] || fail insufficient_overlay_space

WORK="$(mktemp -d /tmp/veci-core022-preflight.XXXXXX)" || fail tmp_unavailable
trap 'rm -rf "$WORK"' EXIT INT TERM
mkdir "$WORK/keys"
for name in "$NEW" "$OLD" "$KEY"; do
    wget -qO "$WORK/$name" "$BASE/$name" || fail release_download_failed
done
check "$WORK/$NEW" "$NEW_SHA" || fail update_integrity_failed
check "$WORK/$OLD" "$OLD_SHA" || fail rollback_integrity_failed
check "$WORK/$KEY" "$KEY_SHA" || fail trust_key_integrity_failed
[ "$(wc -c < "$WORK/$NEW" | tr -d '[:space:]')" = 61691 ] || fail update_size_failed
[ "$(wc -c < "$WORK/$OLD" | tr -d '[:space:]')" = 60424 ] || fail rollback_size_failed
# Ephemeral package-scoped trust; never modify /etc/apk/keys.
for f in /etc/apk/keys/*; do
    [ -f "$f" ] && [ ! -L "$f" ] || continue
    cp "$f" "$WORK/keys/" || fail trusted_key_copy_failed
done
cp "$WORK/$KEY" "$WORK/keys/$KEY"
for name in "$NEW" "$OLD"; do
    apk --keys-dir "$WORK/keys" verify "$WORK/$name" > "$WORK/verify-$name.log" 2>&1 ||
        fail apk_signature_rejected
done
apk --no-network --keys-dir "$WORK/keys" --simulate add "$WORK/$NEW" \
    > "$WORK/install-plan.log" 2>&1 || fail dependency_transaction_blocked
# No additional packages may be installed, removed, or upgraded.
if grep -E 'Installing|Removing|Purging|Upgrading|Downgrading' "$WORK/install-plan.log" |
   grep -Ev 'veci([ -]|$)' >/dev/null 2>&1; then
    fail unrelated_package_in_transaction
fi
echo VECI_022_PHYSICAL_SOURCE_PARITY=pass
echo VECI_022_CORE_RPCD_ACL_PARITY=pass
echo VECI_022_PAIRED_SIGNATURES=pass
echo VECI_022_OFFLINE_APK_SIMULATION=pass
echo VECI_022_ROLLBACK_SIGNED=pass
echo VECI_022_PREFLIGHT=pass
echo VECI_022_PACKAGE_INSTALLED=false
echo VECI_022_FLASH_WRITES=none
echo VECI_022_SMS_LTE_UNCHANGED=true
