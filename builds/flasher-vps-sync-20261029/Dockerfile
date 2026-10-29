ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
# Replace the complete application tree: removed upstream files must not linger.
# The engine and its ARM64 dependencies already match the running VPS exactly.
RUN rm -rf /opt/synthpulse/hermes-webui
ADD webui.tar /opt/synthpulse/hermes-webui/
COPY source-lock.json /opt/synthpulse/runtime-vps-sync.json
COPY runtime-hashes.json /opt/synthpulse/runtime-vps-files.json
ARG WEBUI_REF
ARG VPS_WEBUI_REF
LABEL solutions.synthwave.webui.ref=${WEBUI_REF} \
      solutions.synthwave.webui.vps-ref=${VPS_WEBUI_REF} \
      solutions.synthwave.engine.ref=b59086821cb005d2d8c9890d1bff00b0b7fd2291
RUN python -m compileall -q /opt/synthpulse/hermes-webui/api
USER synthpulse
WORKDIR /opt/synthpulse/hermes-webui
RUN python -c 'import sys; sys.path.insert(0, "/opt/synthpulse/hermes-webui"); from run_agent import AIAgent; import api.routes, api.bot_scout, api.bot_specialists, api.sidebar_organization; import faster_whisper, mnemosyne'
