# J9B — signed app feed and dependency simulation (offline only)

Both J8c artifacts must originate from GitHub Actions run 37913407078. J9 passed SHA256, required package presence, and kernel family comparison; none of those validate package signatures or solve dependency requirements.

J9B audit workflow: .github/workflows/j9b-signed-feed.yml.

It downloads the two artifacts from the same run, rechecks J9, builds pinned upstream APKv3 host tools, extracts the SquashFS filesystem from the candidate firmware into a disposable runner directory, and loads public signing keys **only from that extracted firmware**. It then verifies all four APK indexes, five app wrapper packages, and two kernel module packages against those keys. It never permits untrusted packages.

If and only if signatures and APK metadata all validate, J9B attempts read-only offline apk dependency solver simulations separately for Guest Portal, SQM, DDNS, WireGuard, and Voucher. The simulation runs against a disposable copy of the firmware filesystem, not the physical WE5927.

Missing trusted keys, failed signatures, unsupported metadata, unresolved dependencies, or unavailable host tools must never be interpreted as PASS. The generated j9b-report.json records each result. Even a successful audit execution always marks release_decision NO_GO until live hardware UAT and full firmware updater tests pass.

A green workflow indicates that the audit ran; it does not promise the trust or dependency gate passed. Inspect the report and refuse deployment until all mandatory gates are green, including real UAT. Do not flash, install apps, restart networking, or change the MiFi IMEI on the production router.
