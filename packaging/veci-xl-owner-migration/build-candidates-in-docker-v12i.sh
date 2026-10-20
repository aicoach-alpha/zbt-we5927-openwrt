#!/bin/sh
# VeCI XL v12i: build signed same-name APKv3 CANDIDATES from office-owned capture.
# Must run only in Alpine apk-tools v3 Docker. NO network, NO router deployment.
set -eu
umask 077
LC_ALL=C
export LC_ALL
SOURCE=/source
OUTPUT=/dist
HOOKS=/hooks
KEY=/keys/veci-meter-r2-rsa.key
KEYPUB=/keys/veci-meter-r2-rsa.pem
LIST_ORIGINAL=/source/meta/veci-telco-indonesia.original.list
WORK="$(mktemp -d /tmp/veci-xl-v12i.XXXXXX)"
fail() { printf 'XL_V12I_BUILD=%s\n' "$1"; exit 1; }
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
[ -s "$KEY" ] && [ -s "$KEYPUB" ] || fail signing_key_missing
apk --version | grep -Eq 'apk-tools 3[.]' || fail apk_tools_v3_required
[ -f "$SOURCE/inventory-v12d.json" ] || fail v12d_receipt_missing
[ -f "$SOURCE/meta/counts.txt" ] || fail v12b_metadata_missing
[ -d "$SOURCE/payload" ] || fail captured_payload_missing
[ -d "$OUTPUT" ] || fail output_directory_missing
[ -s "$LIST_ORIGINAL" ] || fail original_package_list_missing
for record in \
 "post-install:10aaaceb1f28a6d7c94833275b7bff3b4f244aa46adb38f335a6234aa07ddad4" \
 "pre-deinstall:5a46723558bc474f6f4e695d0ec30dcbd8a414c701d82d2d480c05dd852d9c62" \
 "post-upgrade:e6cc1bb6d32da1d183ad458231919e55fbab2692a7c5fbd15295ebcab1f6b570"; do
 kind="${record%%:*}"
 expected_digest="${record#*:}"
 [ -s "$HOOKS/$kind.sh" ] || fail original_hook_missing
 actual_digest="$(sha256sum "$HOOKS/$kind.sh" | cut -d " " -f1)"
 [ "$actual_digest" = "$expected_digest" ] || fail original_hook_integrity_failed
 sh -n "$HOOKS/$kind.sh" || fail original_hook_syntax_failed
done
[ ! -e "$OUTPUT/veci-telco-xl-native-0.3.8-r2-mipsel_24kc.apk" ] || fail output_exists
[ ! -e "$OUTPUT/veci-telco-indonesia-0.2.2-r2-mipsel_24kc.apk" ] || fail output_exists

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
for pair in 'veci-telco-xl-native:0.3.7-r1:0.3.8-r2:15' \
            'veci-telco-indonesia:0.2.1-r1:0.2.2-r2:6'; do
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
  # Preserve the OpenWrt generated file-list as the original package shipped it.
  # It was outside the 6 application files and is carried into the new APK.
  if [ "$pkg" = veci-telco-indonesia ]; then
    mkdir -p "$stage/lib/apk/packages"
    cp "$LIST_ORIGINAL" "$stage/lib/apk/packages/veci-telco-indonesia.list"
    [ "$(find "$stage" -type f | wc -l | tr -d "[:space:]")" -eq 7 ] || fail package_metadata_list_missing
    apk mkpkg --files "$stage" \
      --info "name:$pkg" \
      --info "version:$newver" \
      --info arch:mipsel_24kc \
      --info "origin:$pkg" \
      --info license:GPL-2.0-only \
      --info "description:VeCI-versioned-native-$pkg-candidate" \
      --info "depends:$deps_value" \
      --script "post-install:$HOOKS/post-install.sh" \
      --script "post-upgrade:$HOOKS/post-upgrade.sh" \
      --script "pre-deinstall:$HOOKS/pre-deinstall.sh" \
      --sign-key "$KEY" --output "$OUTPUT/$pkg-$newver-mipsel_24kc.apk" || fail mkpkg_failed
    output="$OUTPUT/$pkg-$newver-mipsel_24kc.apk"
  else
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
  fi
  apk --keys-dir /keys verify "$output" >/dev/null || fail candidate_signature_failed
  printf 'XL_V12I_PACKAGE=%s\n' "$pkg"
  printf 'XL_V12I_PAYLOAD_FILES=%s\n' "$count"
  printf 'XL_V12I_SHA256=%s\n' "$(sha256sum "$output" | cut -d ' ' -f1)"
done
echo XL_V12I_BUILD=pass
echo XL_V12I_SIGNATURE=pass
echo XL_V12I_MANIFEST=pass
echo XL_V12I_ORIGINAL_INDONESIA_HOOKS=preserved
 echo XL_V12I_PACKAGE_LIST=preserved
 echo XL_V12I_INSTALL_GATE=blocked_pending_rollback_and_dependency_staging
echo XL_V12I_PRODUCTION=unchanged
