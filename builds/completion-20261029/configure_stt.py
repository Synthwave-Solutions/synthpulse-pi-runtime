#!/usr/bin/env python3
"""Explicit, atomic merge into a chosen customer's Hermes YAML; never prints config."""
import argparse
import os
import tempfile
from pathlib import Path
import yaml

parser = argparse.ArgumentParser()
parser.add_argument("config", type=Path)
args = parser.parse_args()
path = args.config
if path.is_symlink():
    raise SystemExit("Refusing a symlink config path")
config = yaml.safe_load(path.read_text()) if path.exists() else {}
if config is None:
    config = {}
if not isinstance(config, dict):
    raise SystemExit("Expected YAML mapping")
stt = config.setdefault("stt", {})
stt.update(enabled=True, provider="local", language="nl")
local = stt.setdefault("local", {})
local.update(model="/opt/synthpulse/models/whisper-tiny", device="cpu", compute_type="int8",
             language="nl", vad=True, unload_after_idle_seconds=300)
path.parent.mkdir(parents=True, exist_ok=True)
fd, tmp = tempfile.mkstemp(prefix=".stt-config-", dir=path.parent)
try:
    if path.exists():
        old = path.stat()
        os.fchown(fd, old.st_uid, old.st_gid)
    with os.fdopen(fd, "w") as stream:
        yaml.safe_dump(config, stream, sort_keys=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
print("Configured local tiny Whisper (Dutch, CPU int8); other configuration preserved.")
