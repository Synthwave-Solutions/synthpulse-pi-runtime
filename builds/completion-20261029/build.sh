#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
completion_tmp=$(mktemp -d)
trap 'rm -rf "$completion_tmp"' EXIT
completion_base=$(python3 -c 'import json; print(json.load(open("source-lock.json"))["base"]["image"])')
docker image inspect "$completion_base" > "$completion_tmp/base.json"
python3 - "$completion_tmp/base.json" <<'PY'
import json,sys
expected=json.load(open('source-lock.json'))['base'];actual=json.load(open(sys.argv[1]))[0]
assert actual['Architecture']=='arm64','ARM64 base required'
assert actual['Id']==expected['image_id'],'Import the exact SHA-verified desktop base archive first'
PY
# Optional first argument is an already-downloaded completion archive.
if [[ $# -gt 0 ]]; then
  python3 fetch_context.py --archive "$1" --output "$completion_tmp/context"
else
  python3 fetch_context.py --output "$completion_tmp/context"
fi
docker build --pull=false --network=none --build-arg "BASE_IMAGE=$completion_base" \
  -t synthpulse-webui:pi-runtime-completion-20261029 "$completion_tmp/context"
