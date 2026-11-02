# VeCI WE5927 firmware trust root

The public Ed25519 firmware release-signing key is embedded by veci-default-ui
at /etc/veci/firmware-keys/veci-20261102.pub.
The same public key is installed at /etc/opkg/keys/c0465b699a01a426,
because the pinned OpenWrt sysupgrade verifier reads that directory
even on APK-based systems. The finalizer checks both copies.
Expected SHA256: 68a7270d6464cca4b9282f5cf7fa4a84482816fc5e9c0a47c7ae0793fa81e25a.

The private signing key is NOT in Git, an APK, or a firmware image.
The key stays in a NAS private directory mode 0700, file mode 0600,
and needs operator-controlled secure backup before production use.

The package also installs /etc/veci-release-channel. Development mode is
the default; published mode requires explicit VECI_PUBLISHED_RELEASE=1
during controlled build staging. No automatic public publication is done.

The release finalizer checks the actual SquashFS rootfs for this public
trust key and release channel and rejects mismatches, including a
different valid-looking key. A signed firmware is NOT approved for
flashing merely because its local signature verification passed.
The existing router has not yet authenticated or provisioned this new key.

Before physical upgrade: verify device/partition, backup and recovery
procedure, obtain authenticated SSH/operator approval, demonstrate
trusted key chain, run sysupgrade -T, then manually UAT LTE, access,
Guest Portal, Voucher, isolation, and rollback readiness.
Never use sysupgrade -F.
