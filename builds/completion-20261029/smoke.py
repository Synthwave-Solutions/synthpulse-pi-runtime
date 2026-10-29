"""Runs inside the derived image, entirely offline, using public JFK sample audio."""
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import yaml

home = Path(os.environ["HERMES_HOME"])
home.mkdir(parents=True, exist_ok=True)
config = home / "config.yaml"
config.write_text("unrelated_setting: preserve-me\n")
subprocess.run([sys.executable, "/test/configure_stt.py", str(config)], check=True)
cfg = yaml.safe_load(config.read_text())
assert cfg["unrelated_setting"] == "preserve-me"
assert cfg["stt"]["local"]["language"] == "nl"
# The public fixture is English. Override only this disposable test config.
cfg["stt"]["language"] = cfg["stt"]["local"]["language"] = "en"
config.write_text(yaml.safe_dump(cfg))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "/test/jfk.wav", "-c:a", "libopus", "/tmp/stt-fixture.webm"], check=True)
sys.path[:0] = ["/opt/synthpulse/hermes-agent", "/opt/synthpulse/hermes-webui"]
from tools import transcription_tools as stt
from api import upload

available, provider = upload._stt_provider_capability_from_module(stt)
assert available and provider == "local", (available, provider)
audio = Path("/tmp/stt-fixture.webm").read_bytes()
boundary = "synthpulse-tiny-smoke"
body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="recording.webm"\r\n'
        'Content-Type: audio/webm\r\n\r\n').encode() + audio + f'\r\n--{boundary}--\r\n'.encode()
handler = SimpleNamespace(rfile=io.BytesIO(body), headers={"Content-Type": "multipart/form-data; boundary=" + boundary,
                                                      "Content-Length": str(len(body))})
captured = {}
def capture(_handler, result, status=200):
    captured.update(result=result, status=status)
upload.j = capture
upload.handle_transcribe(handler)
assert captured["status"] == 200, captured
assert captured["result"]["ok"] is True, captured
text = captured["result"]["transcript"].lower()
assert "country" in text and "you" in text, captured
print(json.dumps({"webui_capability": provider, "webui_multipart_webm": "passed", "network": "disabled",
                  "transcript": captured["result"]["transcript"], "dutch_config": "validated; fixture is English"}))
