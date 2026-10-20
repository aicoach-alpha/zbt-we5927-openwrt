#!/bin/sh
# VeCI XL v12j: only a signed, offline APKv3 transaction simulation.
# Existing firmware, packages and services are NEVER modified.
set -eu
LC_ALL=C
export LC_ALL
A=/tmp/veci-xl-native-0.3.8-r2-v12j.apk
B=/tmp/veci-telco-indonesia-0.2.2-r2-v12j.apk
fail(){ echo "XL_V12J=$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail root_required
[ -f "$A" ] && [ -f "$B" ] || fail candidate_not_staged
[ ! -L "$A" ] && [ ! -L "$B" ] || fail unsafe_stage_symlink
[ "$(sha256sum "$A" | cut -d ' ' -f1)" = '801b421569f6cd18ade2bfc3a86c7e61e333e680dfc41e29edffd3cdd0793f37' ] || fail xl_checksum_mismatch
[ "$(sha256sum "$B" | cut -d ' ' -f1)" = 'da3d5d9da1bdc684170d75773a03562f7dcca672a3d3d8dd1575969ad4d65866' ] || fail indonesia_checksum_mismatch
echo XL_V12J_SHA256=pass
apk --version | grep -Eq 'apk-tools 3[.]' || fail apk_tools_v3_required
apk info -e veci-telco-xl-native >/dev/null 2>&1 || fail original_xl_package_absent
apk info -e veci-telco-indonesia >/dev/null 2>&1 || fail original_indonesia_package_absent
apk verify "$A" >/dev/null 2>&1 || fail router_signature_verify_failed
apk verify "$B" >/dev/null 2>&1 || fail router_signature_verify_failed
echo XL_V12J_ROUTER_SIGNATURE=pass
echo XL_V12J_SIMULATION_BEGIN
# Do not run apk update, apk upgrade, --force-overwrite, or scripts.
# --simulate opens installed package database read-only.
# --network=false disables remote repository access.
if apk --network=false add --simulate "$A" "$B"; then
 echo XL_V12J_SIMULATE=pass
 echo XL_V12J_INSTALL=not_attempted
 echo XL_V12J_ROUTER=unchanged
else
 echo XL_V12J_SIMULATE=blocked
 echo XL_V12J_INSTALL=not_attempted
 echo XL_V12J_ROUTER=unchanged
 exit 1
fi
