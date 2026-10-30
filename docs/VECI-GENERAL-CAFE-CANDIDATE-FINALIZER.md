# VeCI General-Café offline candidate release gate

After a complete OpenWrt build and no concurrent make process, execute the finalizer on NAS using the pinned source and original build tree:

    python3 /home/andre/projects/veci/worktrees/candidate-finalizer/scripts/finalize-veci-cafe-candidate.py --firmware /home/andre/projects/veci/worktrees/candidate-finalizer --build-tree /mnt/data/andre-maintenance-archives/veci-cafe-build-20261029/openwrt --output /mnt/data/andre-maintenance-archives/veci-cafe-build-20261029/candidate-verified

The output must not already exist. The original OpenWrt SHA must be c740570351512e4400369b3c2aff49741f65580e. The staged firmware build_id must point to a real ancestor Git object, whose source/veci.commit matches the staged Core pin. A matching host fwtool, exact image/manifest count, board/version/size, required LTE + Guest/Voucher package inventory and SHA256 are mandatory.

Output is private: RELEASE-CANDIDATE.json, SHA256SUMS, image and manifest. It does not publish, install apps, access the router, or flash firmware. Success retains FLASH_DECISION=NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT. Firmware source testing is not evidence of bootability or recovery. Verify actual flash partition size and physical rescue before manual upgrade.
