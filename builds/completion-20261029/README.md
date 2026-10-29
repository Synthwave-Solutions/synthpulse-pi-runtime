# Pi runtime completion · 29 October 2026

This supplement adds offline tiny Whisper and five targeted WebUI changes to the
existing VPS-matched clean ARM64 image. The original `builds/vps-20261028`
provenance is unchanged. No customer state, login sessions, keys or account
credentials are included.

- Runtime revision: `pi-runtime-completion-20261029-r1`.
- WebUI source: [f2b925d2](https://github.com/Synthwave-Solutions/hermes-webui/commit/f2b925d2bc500b2a2ffc024a02bbe93e074d6d9d), based on deployed `bebfbc23`.
- Engine remains `b59086821cb005d2d8c9890d1bff00b0b7fd2291`.
- Completion asset: [pi-runtime-completion-20261029.tar.gz](https://github.com/Synthwave-Solutions/synthpulse-pi-runtime/releases/download/synthpulse-pi-vps-20261028/pi-runtime-completion-20261029.tar.gz).
- Asset SHA256: `3b020d2e4be1ac23e0f5575a9ba5e40fe453fdc5721e1dc85e64f8d4b0f85ff5`.

The model and ARM64 CPython 3.14 wheels remain in the release asset, not Git.
`model-lock.json` pins the upstream model revision; `payload-sha256.json` pins
every model file, wheel, source patch and build input. PyAV is pinned to 16.1.0
because 19.0.2 broke the tested Faster Whisper transcription path.

## Fetch and build

Use an ARM64 Docker host with the exact original desktop image imported. Its
archive URL, SHA256 and image ID are recorded in `source-lock.json`. Verify the
archive before `docker load`; `build.sh` refuses a different base image ID or
architecture.

```bash
cd builds/completion-20261029
./build.sh
```

To avoid downloading again, pass the local completion archive:

```bash
./build.sh /absolute/path/pi-runtime-completion-20261029.tar.gz
```

To inspect without building:

```bash
python3 fetch_context.py --output /absolute/path/new-context
```

Fetching verifies the archive SHA256, safe archive members, every payload hash,
and equality with the version-controlled build inputs. The Docker build then
runs with `--network=none --pull=false`. The source patch also checks every
original WebUI file hash before modifying it. A different source version fails
closed rather than restoring old frontend bundles.

The complete five-file source is published in the WebUI commit linked above;
`ui/targeted-changes.patch` records the minimal delta from deployed `bebfbc23`.
The release context supplies those exact committed source files. It can be
independently checked against that commit using `ui/manifest.json`.

This locks the fetched inputs; Docker build timestamps and provenance metadata
can still change an image identifier on an independent rebuild. Validate the
runtime marker, installed source hashes and offline smoke behavior, rather than
assuming the locally observed image ID must repeat byte for byte.

## Runtime acceptance

`/opt/synthpulse/runtime-completion.json` records revision and installed WebUI
file hashes. The workstation installer checks this marker, all five source
hashes, the pinned PyAV version and successful local Whisper model loading.
An older STT-only image does not satisfy the completion probe.

The recorded ARM64 image passed both tests with networking disabled:

```bash
python3 fetch_context.py --output "$PWD/test-context"
docker run --rm --network=none -e HERMES_HOME=/tmp/stt-smoke \
  -v "$PWD/test-context:/test:ro" --entrypoint /opt/synthpulse/hermes-agent/venv/bin/python \
  synthpulse-webui:pi-runtime-completion-20261029 /test/smoke.py
```

The verified test context includes `jfk.wav`; its hash is in
`payload-sha256.json`. The smoke converts
that public English sample to WebM/Opus, calls the actual WebUI multipart
transcription handler, and confirms recognized speech. Production configuration
is Dutch; the disposable fixture alone uses English.

For real memory consolidation and the Explorer API:

```bash
docker run --rm --network=none -e HERMES_HOME=/tmp/memory-smoke \
  -v "$PWD:/test:ro" --entrypoint /opt/synthpulse/hermes-agent/venv/bin/python \
  synthpulse-webui:pi-runtime-completion-20261029 /test/image_memory_smoke.py
```

This creates disposable synthetic state, runs actual Mnemosyne 3.15.1
`force=False` fallback consolidation on three aged memories, and verifies the
resulting episodic summary and consolidation record through the current
Memory Explorer routes. LLM and embeddings are disabled only in that test.
`validation.json` clearly separates this evidence from physical Pi acceptance.

## Configuration and account gates

The supplement makes `local_personal` Memory Explorer available on customer
installations without exposing other people's or HQ memory. Its read-only
views reflect actual consolidation results; the separate maintenance service
must target the same personal bank. `HERMES_WEBUI_MEMDASH=1` and
`HERMES_WEBUI_MEMDASH_BACKEND=local_personal` enable it. A remote hub URL must
not be configured simultaneously.

`SP_WEBUI_LOGIN_SUBTITLE` is an optional escaped deployment label.
`SP_MSP_REQUEST_ONLY_APPS=1` removes direct app toggles and rejects direct state
changes, while explicit app requests use the existing signed MSP endpoint.
Optional app availability and requests require genuine MSP pairing. Until
paired, unavailable/503 is intentional; no fake connected state or automatic
request is created. Customer branding and display preferences are configured
per installation, not forced on every Pi by this image.

After first boot, verify local networking, SSH, actual image identity, WebUI,
gateway, memory scheduling, transcription and backup restore. Tailscale/Pi
Connect, Claude/Codex account authentication, Microsoft Graph consent/SSO,
Nango providers, MSP pairing and customer-isolated backup credentials remain
separate onboarding steps. No source or image release can complete those
account logins without the customer's authorization.
