#!/bin/sh
set -eu
repo="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
source_dir="$(printenv VECI_SOURCE_DIR || true)"
[ -n "$source_dir" ] || { echo "Set VECI_SOURCE_DIR to clean tested VeCI Core r6 checkout" >&2; exit 2; }
pinned="$(tr -d '[:space:]' < "$repo/source/veci.commit")"
actual="$(git -C "$source_dir" rev-parse HEAD)"
[ "$pinned" = "$actual" ] || { echo "Core commit does not match firmware pin" >&2; exit 3; }
[ -f "$source_dir/dist/veci/index.html" ] || { echo "Missing built VeCI dist/veci" >&2; exit 4; }
sh -n "$source_dir/files/rpcd-veci"
python3 -m json.tool "$source_dir/rpcd-acl.json" >/dev/null
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/www/veci" "$tmp/usr/libexec/rpcd" "$tmp/usr/share/rpcd/acl.d"
cp -R "$source_dir/dist/veci/." "$tmp/www/veci/"
for app in guest voucher; do
  mkdir -p "$tmp/www/veci-apps" "$tmp/usr/libexec/rpcd"
  cp "$repo/source/veci-app-$app/files/www/veci-apps/$app.js" "$tmp/www/veci-apps/$app.js"
  install -m 0755 "$repo/source/veci-app-$app/files/usr/libexec/rpcd/veci.app.$app" "$tmp/usr/libexec/rpcd/veci.app.$app"
done

printf "%s\n" "$pinned" > "$tmp/www/veci/veci-core-commit.txt"
install -m 0755 "$source_dir/files/rpcd-veci" "$tmp/usr/libexec/rpcd/veci"
install -m 0644 "$source_dir/rpcd-acl.json" "$tmp/usr/share/rpcd/acl.d/veci.json"
out="$repo/releases/veci-core-r6-hotfix"
mkdir -p "$out"
tar -C "$tmp" --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -czf "$out/veci-core-r6.tar.gz" www usr
( cd "$out" && sha256sum veci-core-r6.tar.gz > SHA256SUMS )
echo "BUNDLE_BUILT_CORE=$pinned"
cat "$out/SHA256SUMS"
