# Native VeCI v2 GUI design guide — WE5927-2SIM

External references reviewed using their actual GitHub repositories:

- kamlendras/muci — simple dashboard, network configuration, hardware/system information and accessible presentation
- benisai/OpenWRT-Moci-BI — responsive vanilla JS SPA, dark glass-like navigational composition, live graph cards, device/network controls
- zhaojh329/oui — modular API separation and fine-grained ACL patterns (its Vue3/Lua-eco toolchain is NOT included in VeCI)
- OppsError404/luci-app-dashboard — truthful kernel traffic, RAM/network metrics, compact live system status

Visual principles implemented in VeCI native (no new frontend stack):
1. Dark professional vertical navigation with responsive mobile drawer.
2. Light, high-contrast dashboard cards and a restrained blue/teal palette.
3. Independent LTE, Wi-Fi, netifd and SMS diagnostic readiness tiles; never imply missing physical UAT passed.
4. Actual observed system metrics, kernel traffic history and topology path.
5. One authoritative backend RPC per action; startup Services and Add-on Profiles have separate ownership.
6. WPA2 onboarding is explicit, UCI-only and requires a separately approved manual reboot. No global network reload from the interface.
7. Keyboard focus visibility, reduced-motion support, mobile card reflow and clear error messaging.

Not copied: LuCI runtime, OUI Vue3/Element Plus, heavy monitoring daemons, vendor UI assets, external images or unreviewed JavaScript. Flash headroom and dependency minimization take priority over adding decorative overhead.

Release limitations: still needs a signed candidate, exact ROM validation, full browser/physical UAT and endurance evidence. No claim that all visible controls have been verified on hardware.
