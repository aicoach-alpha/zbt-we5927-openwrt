#!/bin/sh
# VeCI XL v12f: build signed same-name APKv3 CANDIDATES from office-owned capture.
# Must run only in Alpine apk-tools v3 Docker. NO network, NO router deployment.
set -eu
umask 077
LC_ALL=C
export LC_ALL
SOURCE=/source
OUTPUT=/dist
KEY=/keys/veci-meter-r2-rsa.key
KEYPUB=/keys/veci-meter-r2-rsa.pem
WORK="$(mktemp -d /tmp/veci-xl-v12f.XXXXXX)"
fail() { printf 'XL_V12F_BUILD=%s\n' "$1"; exit 1; }
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
[ -s "$KEY" ] && [ -s "$KEYPUB" ] || fail signing_key_missing
apk --version | grep -Eq 'apk-tools 3[.]' || fail apk_tools_v3_required
[ -f "$SOURCE/inventory-v12d.json" ] || fail v12d_receipt_missing
[ -f "$SOURCE/meta/counts.txt" ] || fail v12b_metadata_missing
[ -d "$SOURCE/payload" ] || fail captured_payload_missing
[ -d "$OUTPUT" ] || fail output_directory_missing
[ ! -e "$OUTPUT/veci-telco-xl-native-0.3.8-r1-mipsel_24kc.apk" ] || fail output_exists
[ ! -e "$OUTPUT/veci-telco-indonesia-0.2.2-r1-mipsel_24kc.apk" ] || fail output_exists

read_dependencies() {
  file="$1"
  # APK output from 'apk info --depends' has a human-readable first header
  # and zero or more dependency specifiers. Don't guess missing dependencies.
  [ -s "$file" ] || return 1
  awk '
    NR == 1 { if ($0 !~ / depends on:$/) exit 12; next }
    NF {
      gsub(/^[ \t]+|[ \t]+$/, "", $0)
      if ($0 !~ /^[-+._:@a-zA-Z0-9<>=~]+$/) exit 13
      printf "%s%s", sep, $0
      sep=" "
    }
    END { print "" }
  ' "$file"
}
for pair in 'veci-telco-xl-native:0.3.7-r1:0.3.8-r1:15' \
            'veci-telco-indonesia:0.2.1-r1:0.2.2-r1:6'; do
  pkg="$(printf '%s' "$pair" | cut -d: -f1)"
  oldver="$(printf '%s' "$pair" | cut -d: -f2)"
  newver="$(printf '%s' "$pair" | cut -d: -f3)"
  expected_count="$(printf '%s' "$pair" | cut -d: -f4)"
  info="$SOURCE/meta/$pkg.info"
  deps="$SOURCE/meta/$pkg.depends"
  paths="$SOURCE/meta/$pkg.paths"
  payload="$SOURCE/payload/$pkg"
  [ -s "$info" ] && [ -s "$deps" ] && [ -s "$paths" ] || fail incomplete_package_metadata
  [ -d "$payload" ] && [ ! -L "$payload" ] || fail package_payload_missing
  grep -Fq "$oldver" "$info" || fail installed_version_unconfirmed
  deps_value="$(read_dependencies "$deps")" || fail original_dependencies_unparseable
  [ "$(find "$payload" -type l | wc -l | tr -d ' ')" -eq 0 ] || fail symlink_payload_rejected
  stage="$WORK/$pkg"
  mkdir -p "$stage"
  cp -a "$payload/." "$stage/" || fail stage_copy_failed
  # The two special exclusions were reconciled in v12d; the APK package
  # inventory is 15 + 6 application files. The .list file is not payload.
  expected="$WORK/$pkg.expected"
  actual="$WORK/$pkg.actual"
  cat "$paths" > "$expected"
  if [ "$pkg" = veci-telco-indonesia ]; then
    printf '%s\n' 'www/luci-static/resources/view/veci/quota.js' >> "$expected"
  fi
  LC_ALL=C sort -u "$expected" -o "$expected"
  (cd "$stage" && find . -type f | sed 's@^\./@@' | LC_ALL=C sort) > "$actual"
  cmp -s "$expected" "$actual" || fail application_manifest_mismatch
  count="$(wc -l < "$actual" | tr -d '[:space:]')"
  [ "$count" -eq "$expected_count" ] || fail captured_file_count_mismatch
  if [ "$pkg" = veci-telco-xl-native ]; then
    [ -s "$stage/usr/libexec/rpcd/veci.xl" ] || fail account_rpc_missing
    [ -s "$stage/usr/share/rpcd/acl.d/veci-xl-owner.json" ] || fail owner_acl_missing
    grep -Fq 'logout) logout_local ;;' "$stage/usr/libexec/rpcd/veci.xl" || fail logout_rpc_missing
    grep -Fq '"logout"' "$stage/usr/share/rpcd/acl.d/veci-xl-owner.json" || fail logout_acl_missing
    sh -n "$stage/usr/libexec/rpcd/veci.xl" || fail rpc_syntax_failed
  else
    [ -s "$stage/usr/libexec/rpcd/veci.quota" ] || fail quota_rpc_missing
    grep -Fq 'veci-xl-quota-session-gate --status' "$stage/usr/libexec/rpcd/veci.quota" || fail quota_guard_missing
    [ -s "$stage/www/luci-static/resources/view/veci/quota.js" ] || fail legacy_view_missing
    printf '%s  %s\n' '4639874ee47a6e8b3f24f1ba4bfb1457bd2e387b6fa95cfa6aabe995a15f8b9f' \
      "$stage/www/luci-static/resources/view/veci/quota.js" | sha256sum -c - >/dev/null || fail legacy_view_checksum_mismatch
    sh -n "$stage/usr/libexec/rpcd/veci.quota" || fail quota_syntax_failed
  fi
  # Check only staged payload; do not change the original snapshot.
  output="$OUTPUT/$pkg-$newver-mipsel_24kc.apk"
  apk mkpkg --files "$stage" \
    --info "name:$pkg" \
    --info "version:$newver" \
    --info 'arch:mipsel_24kc' \
    --info "origin:$pkg" \
    --info 'license:GPL-2.0-only' \
    --info "description:VeCI-versioned-native-$pkg-candidate" \
    --info "depends:$deps_value" \
    --sign-key "$KEY" --output "$output" || fail mkpkg_failed
  apk --keys-dir /keys verify "$output" >/dev/null || fail candidate_signature_failed
  printf 'XL_V12F_PACKAGE=%s\n' "$pkg"
  printf 'XL_V12F_PAYLOAD_FILES=%s\n' "$count"
  printf 'XL_V12F_SHA256=%s\n' "$(sha256sum "$output" | cut -d ' ' -f1)"
done
echo XL_V12F_BUILD=pass
echo XL_V12F_SIGNATURE=pass
echo XL_V12F_MANIFEST=pass
echo XL_V12F_INSTALL_GATE=blocked_original_maintainer_scripts_not_recovered
echo XL_V12F_PRODUCTION=unchanged
