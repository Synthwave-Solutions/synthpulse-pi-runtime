ARG BASE_IMAGE=synthpulse-webui:pi-clean-desktop-20261028
FROM ${BASE_IMAGE}
USER root
COPY wheels /tmp/stt-wheels
RUN /opt/synthpulse/hermes-agent/venv/bin/pip install --no-cache-dir --no-index --find-links=/tmp/stt-wheels faster-whisper==1.2.1 ctranslate2==4.8.4 av==16.1.0 && rm -rf /tmp/stt-wheels
COPY model /opt/synthpulse/models/whisper-tiny
COPY model-lock.json /opt/synthpulse/stt-model-lock.json
RUN chmod -R a+rX /opt/synthpulse/models && /opt/synthpulse/hermes-agent/venv/bin/python -c 'from faster_whisper import WhisperModel; WhisperModel("/opt/synthpulse/models/whisper-tiny",device="cpu",compute_type="int8",local_files_only=True)'
LABEL solutions.synthwave.stt.provider=local solutions.synthwave.stt.model=whisper-tiny
COPY ui /tmp/runtime-completion-ui
RUN python /tmp/runtime-completion-ui/apply_source_patch.py /opt/synthpulse/hermes-webui && rm -rf /tmp/runtime-completion-ui
COPY runtime-completion.json /opt/synthpulse/runtime-completion.json
RUN python -c 'import hashlib,json,pathlib; p=pathlib.Path("/opt/synthpulse"); d=json.loads((p/"runtime-completion.json").read_text()); assert all(hashlib.sha256((p/"hermes-webui"/n).read_bytes()).hexdigest()==h for n,h in d["webui_files"].items())'
LABEL solutions.synthwave.runtime-completion=pi-runtime-completion-20261029-r1
USER synthpulse
