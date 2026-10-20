#!/bin/sh
# VeCI XL v12b: package-owned payload snapshot, tolerant of APK directory entries.
# Read-only on production; writes only a bounded temporary snapshot under /tmp.
set -eu
umask 077
LC_ALL=C; export LC_ALL
ARCHIVE=/tmp/veci-xl-package-origin-v12b-20261020.tar.gz
PACKAGES="veci-telco-xl-native veci-telco-indonesia"
fail() { echo "XL_ORIGIN_V12B=$1"; exit 1; }
[ "$(id -u)" -eq 0 ] || fail root_required
[ ! -e "$ARCHIVE" ] && [ ! -L "$ARCHIVE" ] || fail archive_already_exists
command -v apk >/dev/null 2>&1 || fail apk_unavailable
WORK="$(mktemp -d /tmp/veci-xl-origin-v12b.XXXXXX)" || fail staging_failed
complete=0
cleanup() {
  rm -rf "$WORK"
  [ "$complete" -eq 1 ] || rm -f "$ARCHIVE"
}
trap cleanup EXIT
trap "exit 130" HUP INT TERM
mkdir -m 700 "$WORK/meta" "$WORK/payload" || fail staging_failed
total=0
for pkg in $PACKAGES; do
  apk info -e "$pkg" >/dev/null 2>&1 || fail package_missing
  apk info --contents "$pkg" > "$WORK/meta/$pkg.contents" 2>/dev/null || fail contents_unavailable
  apk info --all "$pkg" > "$WORK/meta/$pkg.info" 2>/dev/null || fail metadata_unavailable
  apk info --depends "$pkg" > "$WORK/meta/$pkg.depends" 2>/dev/null || fail dependencies_unavailable
  apk info --triggers "$pkg" > "$WORK/meta/$pkg.triggers" 2>/dev/null || fail triggers_unavailable
  mkdir -m 700 "$WORK/payload/$pkg" || fail staging_failed
  captured=0
  skipped=0
  dirs=0
  while IFS= read -r raw || [ -n "$raw" ]; do
    case "$raw" in
      ""|*" contains:"|*" contains: ") continue ;;
      /*) raw="$(printf "%s" "$raw" | sed "s@^/@@")" ;;
    esac
    case "$raw" in
      *".."*|*"//"*|*"\"*|*" "*) fail invalid_manifest_path ;;
    esac
    # apk info --contents can list directory entries as well as files.
    case "$raw" in */) dirs=$((dirs+1)); continue ;; esac
    src="/$raw"
    if [ -d "$src" ] && [ ! -L "$src" ]; then
      dirs=$((dirs+1))
      continue
    fi
    # Preserve the complete original manifest while excluding mutable config.
    # Unknown installed regular files are flagged as an explicit rebuild blocker.
    case "$raw" in
      usr/*|www/veci/*|etc/init.d/veci-*|etc/hotplug.d/*|etc/uci-defaults/*) ;;
      *)
        printf "%s\n" "$raw" >> "$WORK/meta/$pkg.excluded-paths"
        skipped=$((skipped+1))
        continue
        ;;
    esac
    if [ ! -f "$src" ] || [ -L "$src" ]; then
      printf "%s\n" "$raw" >> "$WORK/meta/$pkg.excluded-paths"
      skipped=$((skipped+1))
      continue
    fi
    owner="$(apk info -W "$src" 2>/dev/null)" || fail ownership_lookup_failed
    case "$owner" in
      *" is owned by $pkg-"*) ;;
      *) fail unexpected_file_owner ;;
    esac
    bytes="$(wc -c < "$src" | tr -d "[:space:]")" || fail size_failed
    case "$bytes" in ""|*[!0-9]*) fail size_invalid ;; esac
    [ "$bytes" -le 2097152 ] || fail oversized_file
    total=$((total + bytes))
    [ "$total" -le 4194304 ] || fail snapshot_size_limit
    dst="$WORK/payload/$pkg/$raw"
    mkdir -p "$(dirname "$dst")" || fail mkdir_failed
    cp -p "$src" "$dst" || fail file_copy_failed
    [ "$(sha256sum "$src" | cut -d " " -f1)" = "$(sha256sum "$dst" | cut -d " " -f1)" ] || fail file_checksum_failed
    printf "%s\n" "$raw" >> "$WORK/meta/$pkg.paths"
    captured=$((captured+1))
    [ "$captured" -le 160 ] || fail too_many_files
  done < "$WORK/meta/$pkg.contents"
  [ "$captured" -gt 0 ] || fail no_exportable_package_files
  printf "%s %s %s %s\n" "$pkg" "$captured" "$dirs" "$skipped" >> "$WORK/meta/counts.txt"
  printf "XL_ORIGIN_%s_FILES=%s\n" "$(printf "%s" "$pkg" | tr "[:lower:]-" "[:upper:]_")" "$captured"
  printf "XL_ORIGIN_%s_EXCLUDED=%s\n" "$(printf "%s" "$pkg" | tr "[:lower:]-" "[:upper:]_")" "$skipped"
done
printf "%s\n" "Installed package scripts cannot be reconstructed from apk info." > "$WORK/meta/limitations.txt"
tar -czf "$ARCHIVE" -C "$WORK" meta payload || fail archive_failed
chmod 600 "$ARCHIVE" || fail archive_permissions_failed
size="$(wc -c < "$ARCHIVE" | tr -d "[:space:]")" || fail archive_size_failed
case "$size" in ""|*[!0-9]*) fail archive_size_invalid ;; esac
[ "$size" -le 4194304 ] || fail archive_size_limit
complete=1
echo XL_ORIGIN_V12B=ready
echo "XL_ORIGIN_ARCHIVE=$ARCHIVE"
echo "XL_ORIGIN_SHA256=$(sha256sum "$ARCHIVE" | cut -d " " -f1)"
echo "XL_ORIGIN_BYTES=$size"
echo XL_ORIGIN_CONTENT=package_owned_files_and_full_manifest
echo XL_ORIGIN_PRIVATE_CONFIG=excluded
echo XL_ORIGIN_PACKAGE_SCRIPTS=not_recovered
echo XL_ORIGIN_ROUTER=unchanged
