# VeCI firmware release signing

VeCI production firmware uses a persistent OpenWrt `usign` identity for firmware image signing.

## Trust model

- The private release key is never committed to this repository.
- GitHub Actions receives the private and public keys only through repository secrets.
- The release workflow embeds only the public key into the firmware.
- VeCI validates the downloaded sysupgrade image with:
  1. board/target compatibility,
  2. declared size,
  3. SHA256,
  4. `sysupgrade -T`, and
  5. the embedded trusted firmware signature.
- Automatic installation stays unavailable when the trusted public key or signature verifier is absent.
- Automatic installation is opt-in; default policy remains check-only.

## One-time key generation

Generate the key pair on a trusted offline or administrator-controlled Linux system with OpenWrt `usign`:

```sh
umask 077
usign -G \
  -s veci-firmware-release.key \
  -p veci-firmware-release.pub \
  -c "VeCI firmware release signing key"
```

Keep `veci-firmware-release.key` offline after the GitHub secret has been configured.

## GitHub repository secrets

Create these repository Actions secrets:

- `VECI_FIRMWARE_SIGNING_KEY_B64`
- `VECI_FIRMWARE_SIGNING_PUB_B64`

Generate their values without changing the key files:

```sh
base64 -w0 veci-firmware-release.key
echo
base64 -w0 veci-firmware-release.pub
echo
```

The release workflow fails closed if either secret is missing.

## Production release flow

`.github/workflows/publish-veci-release.yml`:

1. resolves the immutable OpenWrt, feed and VeCI source pins;
2. prepares the exact Router Apps package set;
3. restores the persistent firmware signing identity from GitHub Secrets;
4. creates the OpenWrt image certificate;
5. embeds the trusted public key in the firmware;
6. builds firmware and exact-ABI APK feeds together;
7. verifies the produced sysupgrade signature before publication;
8. publishes firmware assets to a GitHub Release;
9. publishes the exact-build package feed under `app-feed/feeds/<build-id>`;
10. updates `app-feed/channel-stable.json`.

Do not publish a production release from an untrusted fork or with a temporary signing key.

## Key rotation

A signing-key rotation requires an overlap release: an already-trusted firmware must first ship the next public key before the following release is signed only by the new key. Do not replace the sole trusted key and release a new image in one step.
