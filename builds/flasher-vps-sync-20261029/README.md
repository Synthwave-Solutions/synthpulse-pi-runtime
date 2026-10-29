# Pinned VPS source update for new Pi installations

This small source layer is applied automatically **after** the reviewed ARM64
runtime completion. It replaces the entire WebUI source tree, preserving the
engine, offline tiny-Whisper model, desktop dependencies and customer-mounted
configuration, memory, accounts and credentials. It does not copy VPS state.

Pins:

- WebUI: `204cfb0f1f2a22f50f510b989a99c62f7379e604` in
  `Synthwave-Solutions/hermes-webui` (VPS code plus reviewed Pi adapters).
- VPS WebUI baseline: `b79a786ca99da3b49e56a2d6a511a710d8eead46`.
- Engine: `b59086821cb005d2d8c9890d1bff00b0b7fd2291`.
- Required base completion: `pi-runtime-completion-20261029-r1`.
- Complete WebUI file manifest: 2,651 files; SHA256
  `01c542f096ecec02ee4641d35c80d9b8b4d0b6b5f7b4b4935f46ae115a1312ca`.

The installer verifies the immutable archive checksum, source-lock commits,
ARM64 architecture, matching engine label and base completion patch hashes.
It builds without network access, checks the complete installed source manifest,
and applies the resulting image to both WebUI and gateway. Existing customer
configuration is retained. Startup failures restore the previous image references.
This hook is for new installations, not an unattended updater for busy systems.

## Published artifact

[Download the pinned context](https://github.com/Synthwave-Solutions/synthpulse-pi-runtime/releases/download/synthpulse-pi-vps-sync-20261029/pi-runtime-vps-sync-20261029.tar.gz).

SHA256: `4f811d2c90650d33d3d9683bc80b8a616c361a60642a348b4cc69751ca7e6043`.
Size: 31,964,458 bytes. It contains exactly `Dockerfile`, `webui.tar`,
`source-lock.json`, and `runtime-hashes.json`. The large archives are release
assets and are intentionally excluded from this source repository.

Do not overwrite this artifact. Future source changes need a new release asset,
its own checksum and an updated reviewed flasher release pin.

## Reproduce the source context

With Git and Python 3.11+, run:

```bash
python3 builds/flasher-vps-sync-20261029/package.py --output /tmp/pi-source-rebuilt.tar.gz
```

The script fetches the exact GitHub commit; it uses the existing Git credentials
(or the installed `gh` credential helper). Supply the appropriate `GH_TOKEN` in
the process environment when authentication is needed; never put it in a URL.
For an existing checkout, add `--source /absolute/path/to/hermes-webui`.
Every archived file must match the committed full manifest, and an existing
output is refused. No release is published by this script.

The original published archive included filesystem timestamps. The script uses
fixed tar/gzip metadata for deterministic future rebuilds, so its compressed
checksum differs from the historical artifact. All four unpacked inputs are
identical; do not substitute the rebuilt gzip for the immutable published asset.

To build on ARM64, safely extract the verified context, select the verified
local completion image and run Docker with `--pull=false --network=none`,
`--build-arg BASE_IMAGE=LOCAL_VERIFIED_TAG`, `--build-arg WEBUI_REF=204cfb0f1f2a22f50f510b989a99c62f7379e604`
and `--build-arg VPS_WEBUI_REF=b79a786ca99da3b49e56a2d6a511a710d8eead46`.
Use `service_stack.ensure_runtime_image` in the flasher for all base and result
checks; no specific physical device's generated image ID is required.

## Physical Pi verification — 29 October 2026

The real flasher helper downloaded the published archive to an isolated recovery
context on the ARM64 Pi, verified the checksum and all 2,651 source files, verified
the base completion and matching engine, then built offline. Latest routes,
Scout, specialists, sidebar organization, Mnemosyne and Whisper imported
successfully. The complete installed source manifest verified successfully.
A second helper call returned the same image without rebuilding.

Test-only image: `sha256:b6c94832e5373924b8bf1bae224d28db18f33a6b85fcff40459b1025a939e0b5`.
No running container was replaced or restarted during this verification;
existing WebUI and gateway remained healthy. Image builds are not evidence of
customer account login, a remote connection or a completed business automation.
