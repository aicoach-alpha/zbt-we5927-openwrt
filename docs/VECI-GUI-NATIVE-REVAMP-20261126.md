# VeCI v2 Native GUI refresh — source review (26 November 2026)

## Root cause in source
- VeCI classic (source/veci-core/veci/index.html, app.css, js/app.js) presented
  page-level Home, Internet, Wi-Fi, Devices, Cellular, Network, System and Apps,
  with a dark sidebar, firmware identity, and clear navigation.
- VeCI v2 compressed many sections into four broad groups and long panels.
- Status data already comes from authenticated native veci.v2 status/internetCheck.

## Reference decisions
| Reference | Verified | Adopted without copying third-party code |
| --- | --- | --- |
| VeCI classic in this repository | Dark sidebar and page-specific destinations | Restore hierarchy and recognisable accent colors |
| https://github.com/kamlendras/muci | Next 14, React 18, Material UI; simplified dashboard | Only dashboard hierarchy; no Next/React runtime |
| https://github.com/benisai/OpenWRT-Moci-BI | Vanilla JS native ubus SPA, live chart and native ACL | Quick navigation, compact metrics, no new runtime |
| https://github.com/zhaojh329/oui | Vue 3, Vite, Lua-eco backend and modular ACL | Keep modular VeCI native RPCs; no Vue or Lua-eco |
| https://github.com/OppsError404/luci-app-dashboard | LuCI metrics and vnStat optional | Status hierarchy; no LuCI or CDN chart dependency |

Third-party source and assets were NOT copied. Current source is original native
VeCI code using existing RPC permissions. See upstream licenses before any reuse.

## Implemented source-only
- New local CSS /veci2/veci-design.css, installed by package Makefile.
- Page-specific sidebar shortcuts and responsive mobile drawer with focus escape.
- Dashboard navigation cards, router-owned live status summaries.
- No additional RPC, no hidden credentials, no auto reboot, no third-party CDN.
- Explicit distinction between Wi-Fi AP runtime and beacon/client/internet proof.

## Acceptance before deployment
1. HTML shortcuts resolve to a real existing panel; no duplicate IDs.
2. Node syntax, v2 GUI and package tests pass.
3. Browser UAT desktop/mobile, authenticated live status, real Wi-Fi/LTE/SMS.
4. No firmware rebuild or flash solely to replace CSS/nav.
5. Protect existing live LTE and Wi-Fi baseline and ongoing 72-hour UAT.
