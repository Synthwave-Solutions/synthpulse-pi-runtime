#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
cache=$(mktemp -d)
trap 'rm -rf "$cache"' EXIT
for component in engine webui; do
 read -r repo ref < <(python3 - "$component" <<'PY'
import json,sys
p=json.load(open('source-lock.json'))[sys.argv[1]];print(p['repo'],p['commit'])
PY
 )
 gh repo clone "$repo" "$cache/$component" -- --no-checkout
 git -C "$cache/$component" archive "$ref" > "$component.tar"
done
curl -fL https://github.com/trycua/cua/releases/download/cua-driver-rs-v0.21.0/cua-driver-rs-0.21.0-linux-arm64-binary.tar.gz -o cua-driver.tar.gz
docker build -f Dockerfile -t synthpulse-webui:pi-clean-20261028 .
docker build -f Dockerfile.desktop --build-arg BASE_IMAGE=synthpulse-webui:pi-clean-20261028 -t synthpulse-webui:pi-clean-desktop-20261028 .
