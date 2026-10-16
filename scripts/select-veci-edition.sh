#!/bin/sh
# Operates only on a checked-out OpenWrt BUILD WORKSPACE. Never on a router.
set -eu
edition="${1:-}"
config="${2:-}"
case "$edition" in general|indonesia) ;; *) echo "usage: $0 general|indonesia /path/to/.config" >&2; exit 2 ;; esac
[ -f "$config" ] || { echo "missing build .config" >&2; exit 2; }
root="$(CDPATH= cd -- "$(dirname -- "$config")" && pwd)"
# General must not stage or include the Indonesia-only package.
if [ "$edition" = general ] && { [ -e "$root/package/veci-telco-indonesia" ] || [ -e "$root/package/veci-telco-xl-native" ]; }; then
	echo "general build unexpectedly contains Indonesia package source" >&2
	exit 1
fi
if [ "$edition" = indonesia ] && [ ! -f "$root/package/veci-telco-indonesia/Makefile" ]; then
	echo "Indonesia package source has not been staged" >&2
	exit 1
fi
if [ "$edition" = indonesia ] && [ ! -f "$root/package/veci-telco-xl-native/Makefile" ]; then
	echo "Indonesia native XL package source has not been staged" >&2
	exit 1
fi
# Remove both forms before setting an explicit, reproducible profile.
sed -i '/^CONFIG_PACKAGE_veci-telco-indonesia=/d;/^# CONFIG_PACKAGE_veci-telco-indonesia is not set$/d' "$config"
# Runtime is manually installable only after operator access is approved.
# Even the Indonesia edition does not enable it automatically.
sed -i '/^CONFIG_PACKAGE_veci-telco-xl-native=/d;/^# CONFIG_PACKAGE_veci-telco-xl-native is not set$/d' "$config"
printf '# CONFIG_PACKAGE_veci-telco-xl-native is not set\n' >> "$config"
if [ "$edition" = indonesia ]; then
	printf 'CONFIG_PACKAGE_veci-telco-indonesia=y\n' >> "$config"
else
	printf '# CONFIG_PACKAGE_veci-telco-indonesia is not set\n' >> "$config"
fi
echo "selected VeCI $edition profile in build config"
