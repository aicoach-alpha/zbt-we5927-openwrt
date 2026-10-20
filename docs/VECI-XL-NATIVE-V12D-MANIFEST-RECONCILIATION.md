# Native XL v12d package payload reconciliation

Snapshot v12b completed on the office laptop on 2026-10-20 with SHA-256:
`6026d5d1d4a9ebb8022470994c9c7d01904cd3fc41095de50e0488955cb6a2f8`.

The original package inventory was:

| Original APK | Captured package files | Previously excluded |
| --- | ---: | ---: |
| `veci-telco-xl-native 0.3.7-r1` | 15 | 0 |
| `veci-telco-indonesia 0.2.1-r1` | 5 | 2 |

The two explicit excluded entries are:

1. `lib/apk/packages/veci-telco-indonesia.list`: an OpenWrt package file-list generated during package assembly, used by OpenWrt install/upgrade hooks. Its exact current contents are archived as local metadata for comparison, **not blindly reused as a binary source file**. In a proper OpenWrt source build, OpenWrt regenerates this file from actual package contents.
2. `www/luci-static/resources/view/veci/quota.js`: an existing package-owned static LuCI quota view. The v12d capture stores an **exact byte-for-byte** copy solely to avoid dropping functionality during a future same-name rebuild. No code changes to LuCI are authorized.

## Local office workflow
Run `scripts/veci-xl-v12d-reconcile-original-payload-office-20261020.ps1`. This reads the v12c `inventory.json` and two excluded path names, checks ownership and SHA-256 directly on the office-connected router, copies only these two files, checks the copied hashes and adds:

- `staged-v12b/payload/veci-telco-indonesia/www/luci-static/resources/view/veci/quota.js`
- `staged-v12b/meta/veci-telco-indonesia.original.list`
- `staged-v12b/inventory-v12d.json`

The script does not issue APK operations, restart RPC, or change router files. It does not send subscriber data to any service.

## Rebuild policy
The full application payload is expected to reach 15 native XL files and 6 Telco Indonesia files (21 regular files), while the `.list` file is build-generated metadata. Do not upload privately captured files or proprietary binaries to a public GitHub repository without authorization.

**Do not install** the prior standalone `veci-xl-core-policy` APK: package ownership conflicts are confirmed. Next: reconcile original APK installation scripts and dependency metadata; then construct **same-name, higher-version, signed packages** that retain their complete original payload and owned paths. Compare candidate file lists to original package manifests before deploying. Never force overwrites, remove the old packages, or flash firmware as a workaround.
