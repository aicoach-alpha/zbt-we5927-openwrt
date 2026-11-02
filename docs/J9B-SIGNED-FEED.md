# J9B — signed app feed and dependency simulation (offline only)

Both J8c artifacts must originate from GitHub Actions run 37913407078. J9 passed SHA256, required package presence, and kernel family comparison; none of those validate package signatures or solve dependency requirements.

J9B audit workflow: .github/workflows/j9b-signed-feed.yml.

It downloads the two artifacts from the same run, rechecks J9, builds pinned upstream APKv3 host tools, extracts the SquashFS filesystem from the candidate firmware into a disposable runner directory, and loads public signing keys **only from that extracted firmware**. It then verifies the four signed APK repository indexes against those keys. Individual APK signatures are checked separately for diagnostics, but OpenWrt's APKv3 trust model can authenticate unsigned standalone APKs through a signed index that binds their content hashes. These hashes must be enforced by the repository transaction; standalone unsigned APKs must NEVER be installed as untrusted files.

If and only if the four index signatures and APK metadata all validate, J9B runs a read-only dependency solver simulation on the extracted firmware (separately for Guest Portal, SQM, DDNS, WireGuard, and Voucher), then fetches all five wrappers plus two kernel modules from the signed local indexes to verify their payloads. All resulting writes remain confined to the disposable GitHub runner. The simulation runs against a disposable copy of the firmware filesystem, not the physical WE5927.

Missing trusted keys, failed signatures, unsupported metadata, unresolved dependencies, or unavailable host tools must never be interpreted as PASS. The generated j9b-report.json records each result. Even a successful audit execution always marks release_decision NO_GO until live hardware UAT and full firmware updater tests pass.

A green workflow indicates that the audit ran; it does not promise the trust or dependency gate passed. Inspect the report and refuse deployment until all mandatory gates are green, including real UAT. Do not flash, install apps, restart networking, or change the MiFi IMEI on the production router.

J8c discovery (2026-10-12): all 4 repository indexes verified with 2 keys extracted from the firmware; 7 APKs did not individually verify. This alone does not constitute a broken or trusted feed: trust of package CONTENT through the indexes and real solver/fetch checks are still required. No hardware flashing is authorized.

## J8c actual findings (12 October 2026)

- J8c GitHub run: 37913407078 (kernel 6.12.112).
- 2 firmware public keys discovered in the extracted SquashFS.
- 4/4 index signatures PASS against extracted keys.
- 11/11 selected metadata parse PASS.
- 7/7 selected package payload fetches PASS against signed local repositories (5 app wrappers + 2 kernel modules).
- 5/5 APKv3 solver simulations PASS against the disposable extracted firmware rootfs.
- Individual detached package signatures: 0/7, informational under signed-index trust model; do not sideload as untrusted packages.
- CI source and evidence: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38193984721.
- **OFFLINE PASS** does not mean firmware updater, voucher expiry, guest isolation, package postinstall, WAN/LTE, or recovery has passed on a device. **FLASH NO_GO.**
