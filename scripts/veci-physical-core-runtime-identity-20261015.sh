#!/bin/sh
# Strictly read-only physical identity inventory before a package-managed VeCI upgrade.
# Execute only through the authorized office laptop, never andre-nas.
# No SMS read, modem command, service restart, package install, or credentials export.
set -eu
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
[ "$#" = 1 ] && [ "$1" = --status ] || { echo usage: --status >&2; exit 2; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || {
    echo VECI_RELEASE_BOARD=wrong_device; exit 1;
}
grep -q "^DISTRIB_RELEASE='25.12.5'$" /etc/openwrt_release || {
    echo VECI_RELEASE_OPENWRT=unsupported; exit 1;
}
for c in apk awk df grep id sha256sum ubus; do
    command -v "$c" >/dev/null 2>&1 || {
        echo VECI_RELEASE_PREFLIGHT=missing_system_tool; exit 1;
    }
done
echo VECI_RELEASE_BOARD=pass
echo VECI_RELEASE_OPENWRT=25.12.5
if apk list -I 2>/dev/null | grep -q '^veci-0[.]2[.]0-r1'; then
    echo VECI_RELEASE_INSTALLED_CORE=0.2.0
else
    echo VECI_RELEASE_INSTALLED_CORE=unexpected
fi
hash_file() {
    name="$1"
    path="$2"
    if [ -f "$path" ] && [ ! -L "$path" ]; then
        printf 'VECI_RELEASE_%s_SHA256=' "$name"
        sha256sum "$path" | awk '{ print $1 }'
    else
        printf 'VECI_RELEASE_%s_SHA256=missing_or_symlink\n' "$name"
    fi
}
hash_file CELLULAR /www/veci/js/pages/cellular.js
hash_file QUOTA_MODULE /www/veci/js/lib/native-quota.js
hash_file RPCD /usr/libexec/rpcd/veci
hash_file CORE_ACL /usr/share/rpcd/acl.d/veci.json
hash_file CONFIG /etc/config/veci
hash_file SMS_CSS /www/veci/sms-center.css
# Guard native backend files that a full core APK transaction would replace.
# Deviations require a source-preserving package revision, never a bypass.
BACKEND_OK=true
if [ -f /usr/libexec/rpcd/veci ] && [ ! -L /usr/libexec/rpcd/veci ] &&
   [ "$(sha256sum /usr/libexec/rpcd/veci | awk '{print $1}')" = 2b83fac1da487188617888757a2b769d6ed9bf94d32aeaa9a87139b008f913da ]; then
    echo VECI_RELEASE_CORE_RPCD_PARITY=pass
else
    echo VECI_RELEASE_CORE_RPCD_PARITY=drift
    BACKEND_OK=false
fi
if [ -f /usr/share/rpcd/acl.d/veci.json ] &&
   [ ! -L /usr/share/rpcd/acl.d/veci.json ] &&
   [ "$(sha256sum /usr/share/rpcd/acl.d/veci.json | awk '{print $1}')" = 1c59a295448483147507d58336a554db96803aebf4eff8263bc73e89ace6eb5b ]; then
    echo VECI_RELEASE_CORE_ACL_PARITY=pass
else
    echo VECI_RELEASE_CORE_ACL_PARITY=drift
    BACKEND_OK=false
fi
if [ "$BACKEND_OK" = true ]; then
    echo VECI_RELEASE_BACKEND_BASELINE=compatible
else
    echo VECI_RELEASE_BACKEND_BASELINE=blocked_pending_reconciliation
fi
if ubus -S call veci.quota status >/dev/null 2>&1; then
    echo VECI_RELEASE_BACKEND_QUOTA=pass
else
    echo VECI_RELEASE_BACKEND_QUOTA=unavailable
fi
if ubus -S call veci.cellular status >/dev/null 2>&1; then
    echo VECI_RELEASE_BACKEND_CELLULAR=pass
else
    echo VECI_RELEASE_BACKEND_CELLULAR=unavailable
fi
df -k /overlay | awk 'NR==2 { print "VECI_RELEASE_OVERLAY_FREE_KB=" $4 }'
echo VECI_RELEASE_PREFLIGHT=read_only
echo VECI_RELEASE_PACKAGE_TRANSACTION=not_started
echo VECI_RELEASE_SERVICE_RESTARTS=false
echo VECI_RELEASE_LTE_SMS_UNCHANGED=true
