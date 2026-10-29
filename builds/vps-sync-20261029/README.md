# AddContract Pi: current VPS WebUI, 29 October 2026

The previous Pi image was based on WebUI `bebfbc23`. The running VPS now uses
`b79a786c`, which adds personal Scout management, bot specialists, nested chat
sections, background task improvements and updated Memory Explorer UI.

This build replaces the whole WebUI source tree with `204cfb0f`: the exact VPS
revision plus the existing optional Pi adapters for local personal memory,
customer login branding and request-only MSP apps. No customer state or VPS
credentials are copied. The source is published in
`Synthwave-Solutions/hermes-webui`, branch `addcontract/pi-vps-sync-20261029`.
Its subsequent `c3f6e196` commit only adjusts tests; runtime files are identical.

The Hermes engine remains `b5908682`: all 17,481 tracked engine files on the Pi
were compared with the clean VPS checkout and match byte for byte. Keep the
tested ARM64 tiny-Whisper dependencies and existing browser drivers in the base.
`source-lock.json` is the authoritative source record for this image, superseding
the inherited completion metadata's WebUI file hashes.

## Rebuild and deploy

On an ARM64 Docker host, provide the exact base image from `source-lock.json` and
a checkout containing the published WebUI commit:

```bash
bash build.sh /absolute/path/to/hermes-webui
```

The script verifies the base architecture, tags the exact local image and builds
without network access. Image labels record both the VPS baseline and Pi source
commit. Existing mounted configuration, accounts, sessions, OAuth state, local
memory, router and services remain customer-specific.

`deploy.py IMAGE` is intentionally restricted to the existing AddContract Pi.
Run as root only after checking that WebUI chats are idle. It checks the current
image, stops WebUI and gateway, makes a private state/configuration backup and
verifies the archive, then replaces both images and waits for both health checks.
An error restores the previous image reference. It does not silently replace
post-upgrade data with a backup; retain both versions for manual recovery if a
future release makes incompatible state migrations.

Other customer installations should use their own deployment procedure and
backups. This source overlay is not silently substituted for an existing
immutable flasher release asset.

## Verification

The source verification covered 251 passing WebUI tests, including local memory,
MSP apps, password login and the latest bot specialists; one optional real-memory
test was skipped in the isolated test environment. The two current engine
regressions passed with isolated state. The new ARM64 image compiled/imported
the backend and served an isolated login page with HTTP 200 before deployment.
See `validation.json` for physical Pi acceptance results.
