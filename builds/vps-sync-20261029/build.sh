#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
source_repo=${1:?Usage: build.sh /path/to/committed/hermes-webui}
read -r baseline ref vps_ref < <(python3 - <<'PY'
import json
d=json.load(open('source-lock.json'))
print(d['base_image'],d['webui_commit'],d['vps_webui_commit'])
PY
)
test "$(docker image inspect "$baseline" --format '{{.Architecture}}')" = arm64
docker tag "$baseline" synthpulse-webui:verified-base-672a2c73ac30
git -C "$source_repo" archive "$ref" > webui.tar
trap 'rm -f webui.tar' EXIT
docker build --network=none --pull=false --build-arg BASE_IMAGE=synthpulse-webui:verified-base-672a2c73ac30 \
  --build-arg "WEBUI_REF=$ref" --build-arg "VPS_WEBUI_REF=$vps_ref" \
  -t synthpulse-webui:pi-vps-sync-20261029 .
