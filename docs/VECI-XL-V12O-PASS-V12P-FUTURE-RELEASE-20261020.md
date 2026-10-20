# VeCI v12o PASS and v12p guarded future release delivery — 2026-10-20

## Verified v12o office result

Owner executed the signed snapshot publisher successfully:

```text
XL_V12O_BUILD=pass
XL_V12O_SIGNATURE=pass
XL_V12O_ARCHIVES=2
XL_V12O_INDEX_SHA256=d4dfe6c213c6fd7ebb92e50189511b1e941105e0a43fd5ef47aae054a43525ea
XL_V12O_OFFICE=pass
XL_V12O_NATIVE_VERSION=0.3.8-r2
XL_V12O_INDONESIA_VERSION=0.2.2-r2
XL_V12O_RELEASE_PATH=C:\veci-build\xl-native-feed-releases\native-0.3.8-r2__indonesia-0.2.2-r2
XL_V12O_PRODUCTION=unchanged
```

The v12o index is identical in SHA-256 to the previously live v12n index. Therefore no production install, package upgrade, additional v12o simulation or repeat UAT is justified.

## New implementation: v12p guarded release roll-forward

- Router script: `packaging/veci-xl-owner-migration/v12p-guarded-rollforward.sh`.
- Office wrapper: `packaging/veci-xl-owner-migration/v12p-guarded-rollforward-office.ps1`.

**Only for a genuinely new future signed snapshot:** the wrapper checks the published `release-receipt.txt` SHA-256 values, stages two canonical APKs and signed `Packages.adb`, then calls the router with `-Apply`. Router code rejects same-version binary repacks, verifies signatures with the already-installed VeCI key, and returns `XL_V12P_ACTION=noop_same_versions` if both package versions already match. When an upgrade is required, it runs **one** offline `apk upgrade --simulate` only for the two installed package names, refuses any other solver action, stores the previous feed, world and non-target package inventory, then uses the same offline repository override for the real scoped upgrade. One integrity check verifies versions, world, unchanged non-target packages and index SHA-256. Automatic rollback is attempted when actual upgrade or post-upgrade integrity fails. Rollback is a best-effort restoration and reports failures rather than claiming complete recovery.

The script does **not** use `apk upgrade` without target names; it does not flash firmware, touch modem, SMS, USSD, or authenticate to XL. Source/static guards were checked. **The actual newer-version transaction and rollback have NOT been tested on production because no new version exists.**

## Usage when a new release exists

```powershell
$p="$env:TEMP\veci-xl-v12p.ps1"
curl.exe -fLsS https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/3301d03c59ad925aa4c096bec1435c55c1c0fa53/packaging/veci-xl-owner-migration/v12p-guarded-rollforward-office.ps1 -o $p
if ($LASTEXITCODE -eq 0) { & $p -Apply -ReleasePath "C:\veci-build\xl-native-feed-releases\<NEW_VERSION_SNAPSHOT>" }
```

Do not run this against v12o; it is a same-version snapshot and will not improve the router. Only perform a real `-Apply` after genuine newer signed owner APKs are available, with owner confirmation of the intended upgrade.

## Carrier quota

`operator_config_required` remains correct and carrier-origin quota is not LIVE. Acquiring a permitted XL/XLSMART API/consent mechanism is external work, not solved by signing a feed index. Prior v12o quota safety code is source-only until an independently versioned UI/adapter package is deployed.
