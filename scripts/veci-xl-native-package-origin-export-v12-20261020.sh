#!/bin/sh
# VeCI XL v12: snapshot ORIGINAL installed package payloads and metadata.
# Only /tmp writes. No credentials or runtime session/cache dirs.
set -eu
umask 077
LC_ALL=C; export LC_ALL
ROOT=/tmp/veci-xl-package-origin-20261020
ARCHIVE=/tmp/veci-xl-package-origin-20261020.tar.gz
PACKAGES='veci-telco-xl-native veci-telco-indonesia'
fail(){ echo "XL_ORIGIN=$1"; exit 1; }
[ "$(id -u)" -eq 0 ] || fail root_required
[ ! -e "$ROOT" ] && [ ! -L "$ROOT" ] || fail snapshot_already_exists
[ ! -e "$ARCHIVE" ] && [ ! -L "$ARCHIVE" ] || fail archive_already_exists
command -v apk >/dev/null 2>&1 || fail apk_unavailable
mkdir -m 700 "$ROOT" || fail staging_failed
mkdir -m 700 "$ROOT/meta" "$ROOT/payload" || fail staging_failed
successful=0
cleanup(){
 if [ "$successful" = 0 ]; then rm -f "$ARCHIVE"; rm -rf "$ROOT"; fi
}
trap cleanup 0 HUP INT TERM
total=0
for pkg in $PACKAGES; do
 apk info -e "$pkg" >/dev/null 2>&1 || fail package_missing
 apk info --contents "$pkg" > "$ROOT/meta/$pkg.contents" 2>/dev/null || fail contents_unavailable
 apk info --all "$pkg" > "$ROOT/meta/$pkg.info" 2>/dev/null || fail metadata_unavailable
 apk info --depends "$pkg" > "$ROOT/meta/$pkg.depends" 2>/dev/null || fail dependencies_unavailable
 apk info --triggers "$pkg" > "$ROOT/meta/$pkg.triggers" 2>/dev/null || fail triggers_unavailable
 mkdir -m 700 "$ROOT/payload/$pkg" || fail staging_failed
 count=0
 while IFS= read -r raw || [ -n "$raw" ]; do
   case "$raw" in
     ''|*' contains:') continue ;;
     /*) raw="$(printf '%s' "$raw" | sed 's@^/@@')" ;;
   esac
   case "$raw" in
     usr/*|www/veci/*) ;;
     *) fail unapproved_installed_path ;;
   esac
   case "$raw" in
     *'..'*|*'//'*|*'\'*|*' '*) fail invalid_manifest_path ;;
   esac
   src="/$raw"
   [ -f "$src" ] && [ ! -L "$src" ] || fail installed_file_missing_or_symlink
   owner="$(apk info -W "$src" 2>/dev/null)" || fail ownership_lookup_failed
   case "$owner" in
     *" is owned by $pkg-"*) ;;
     *) fail unexpected_file_owner ;;
   esac
   bytes="$(wc -c < "$src" | tr -d '[:space:]')" || fail file_size_failed
   case "$bytes" in ''|*[!0-9]*) fail file_size_invalid ;; esac
   [ "$bytes" -le 2097152 ] || fail oversized_file
   total=$((total+bytes))
   [ "$total" -le 4194304 ] || fail snapshot_size_limit
   dst="$ROOT/payload/$pkg/$raw"
   mkdir -p "$(dirname "$dst")" || fail mkdir_failed
   cp -p "$src" "$dst" || fail capture_failed
   [ "$(sha256sum "$src" | cut -d ' ' -f1)" = "$(sha256sum "$dst" | cut -d ' ' -f1)" ] || fail payload_hash_mismatch
   printf '%s\n' "$raw" >> "$ROOT/meta/$pkg.paths"
   count=$((count+1))
   [ "$count" -le 160 ] || fail excessive_file_count
 done < "$ROOT/meta/$pkg.contents"
 [ "$count" -gt 0 ] || fail empty_package_manifest
 printf '%s %s\n' "$pkg" "$count" >> "$ROOT/meta/file-counts.txt"
 printf 'XL_ORIGIN_%s_FILES=%s\n' "$(printf '%s' "$pkg" | tr '[:lower:]-' '[:upper:]_')" "$count"
done
printf '%s\n' 'scripts=not_exported_from_installed_database' > "$ROOT/meta/rebuild-limitations.txt"
tar -czf "$ARCHIVE" -C "$ROOT" meta payload || fail tar_failed
chmod 600 "$ARCHIVE" || fail archive_permission_failed
size="$(wc -c < "$ARCHIVE" | tr -d '[:space:]')"
case "$size" in ''|*[!0-9]*) fail archive_size_invalid ;; esac
[ "$size" -le 4194304 ] || fail archive_size_limit
successful=1
echo XL_ORIGIN=ready
echo "XL_ORIGIN_ARCHIVE=$ARCHIVE"
echo "XL_ORIGIN_SHA256=$(sha256sum "$ARCHIVE" | cut -d ' ' -f1)"
echo "XL_ORIGIN_BYTES=$size"
echo XL_ORIGIN_CONTENT=package_owned_payload_and_metadata
echo XL_ORIGIN_INSTALL_SCRIPTS=not_recovered
echo XL_ORIGIN_ROUTER=unchanged
