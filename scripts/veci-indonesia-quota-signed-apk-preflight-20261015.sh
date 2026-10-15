#!/bin/sh
# VeCI Indonesia 0.2.1 one-time signed APK trust/dependency PREFLIGHT.
# Physical execution via OFFICE laptop ONLY. Read-only on router: /tmp files.
# NO key enrollment, installation, modem/SMS reads, reboot or flash writes.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL
fail() {
    printf 'VECI_SIGNED_APK_PREFLIGHT=blocked\n'
    printf 'VECI_SIGNED_APK_REASON=%s\n' "$1"
    printf 'VECI_SIGNED_APK_INSTALLED=false\n'
    exit 1
}
[ "$#" -eq 1 ] && [ "$1" = "--verify" ] || fail usage
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = "zbtlink,zbt-we5927" ] || fail wrong_board
grep -q "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_os_release
for bin in apk wget sha256sum awk mktemp cp grep wc df; do
    command -v "$bin" >/dev/null 2>&1 || fail missing_utility
done
free_kib="$(df -k /overlay 2>/dev/null | awk 'NR==2{print $4}')"
case "$free_kib" in ''|*[!0-9]*) fail overlay_unreadable ;; esac
[ "$free_kib" -ge 256 ] || fail insufficient_overlay
# Avoid automatic changes of other packages. This view is intentionally
# compatible with the existing LuCI installation; all deps must be installed.
for dep in rpcd luci-base jsonfilter; do
    apk info -e "$dep" >/dev/null 2>&1 || fail missing_existing_dependency
done
work="$(mktemp -d /tmp/veci-quota-signed.XXXXXX)" || fail tmp_full
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT TERM
mkdir "$work/keys" "$work/empty"
tag=veci-indonesia-quota-signed-a0b5b97ff9a2
base="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$tag"
pkg="$work/veci-telco-indonesia-0.2.1-r1.apk"
key="$work/keys/veci-quota-candidate.pem"
wget -qO "$pkg" "$base/veci-telco-indonesia-0.2.1-r1.apk" || fail package_unavailable
wget -qO "$key" "$base/veci-quota-candidate.pem" || fail key_unavailable
hash_pkg="$(sha256sum "$pkg" | awk '{print $1}')"
hash_key="$(sha256sum "$key" | awk '{print $1}')"
[ "$hash_pkg" = "da72b09afefcd2bdf99bc501d86bd8e485f6a7156b8ccdaae189449a3b0ce34f" ] || fail package_hash
[ "$hash_key" = "4d1bae271c4cca9b46ac10404d887c246637795f5b89d271fa38672efe9bdbfa" ] || fail key_hash
[ "$(wc -c < "$pkg" | tr -d '[:space:]')" = 5683 ] || fail package_size
[ "$(wc -c < "$key" | tr -d '[:space:]')" = 178 ] || fail key_size
printf 'VECI_SIGNED_APK_SHA256=pass\n'
# Trust only for this command: never modify /etc/apk/keys or repos.
# Copy already trusted *public* system keys into private /tmp keyring so
# any existing repos can still be consulted without weakening validation.
for old in /etc/apk/keys/*; do
    [ -f "$old" ] && [ ! -L "$old" ] || continue
    cp "$old" "$work/keys/" || fail trusted_key_copy
done
if ! apk --keys-dir "$work/keys" verify "$pkg" >"$work/verify.log" 2>&1; then
    fail package_signature_not_verified
fi
printf 'VECI_SIGNED_APK_SIGNATURE=pass\n'
if ! apk --keys-dir "$work/keys" --simulate add "$pkg" >"$work/simulation.log" 2>&1; then
    if grep -Eiq 'untrusted|signature' "$work/simulation.log"; then
        fail package_signature_or_feed_trust
    elif grep -Eiq 'unsatisfiable|conflict|missing|no such|not found' "$work/simulation.log"; then
        fail dependency_solver_blocked
    else
        fail package_manager_simulation_blocked
    fi
fi
# Block attempted changes to existing packages even if solver says success.
if grep -Eiq '(^|[[:space:]])(Upgrading|Downgrading|Purging|Removing)[[:space:]]' "$work/simulation.log"; then
    fail unexpected_package_changes
fi
printf 'VECI_SIGNED_APK_DEPENDENCY_SIMULATION=pass\n'
printf 'VECI_SIGNED_APK_PREFLIGHT=pass\n'
printf 'VECI_SIGNED_APK_INSTALLED=false\n'
printf 'VECI_MODEM_AND_SMS_UNCHANGED=true\n'
printf 'VECI_FLASH_WRITES=none\n'
printf 'VECI_XL_ACCOUNT_LOGIN=not_attempted\n'
printf 'VECI_OPERATOR_QUOTA=not_verified\n'
