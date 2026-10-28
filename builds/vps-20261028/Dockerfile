FROM node:22-trixie-slim AS node
FROM python:3.14-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends git curl build-essential tini && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && npm install -g @openai/codex@0.162.1 @anthropic-ai/claude-code@2.1.296 && node /usr/local/lib/node_modules/@anthropic-ai/claude-code/install.cjs && claude --version && npm cache clean --force
ADD engine.tar /opt/synthpulse/hermes-agent/
ADD webui.tar /opt/synthpulse/hermes-webui/
RUN python -m venv /opt/synthpulse/hermes-agent/venv && /opt/synthpulse/hermes-agent/venv/bin/pip install --no-cache-dir -e '/opt/synthpulse/hermes-agent[mcp]' -r /opt/synthpulse/hermes-webui/requirements.txt mnemosyne-hermes==0.5.0 mnemosyne-memory==3.15.1 fastembed==0.8.0 sqlite-vec==0.1.9 aiohttp==3.14.3
ENV HERMES_WEBUI_AGENT_DIR=/opt/synthpulse/hermes-agent HERMES_WEBUI_PYTHON=/opt/synthpulse/hermes-agent/venv/bin/python SP_WEBUI_DIR=/opt/synthpulse/hermes-webui HERMES_WEBUI_DISABLE_LOCAL_VENV=1 HERMES_WEBUI_AUTO_INSTALL=0 HERMES_WEBUI_HOST=0.0.0.0 HERMES_WEBUI_PORT=8787 HERMES_HOME=/home/synthpulse/.synthpulse-engine
ENV PATH=/opt/synthpulse/hermes-agent/venv/bin:$PATH
RUN useradd -m -u 1000 -s /bin/bash synthpulse && mkdir -p /home/synthpulse/.synthpulse-engine && chown -R synthpulse:synthpulse /home/synthpulse
COPY webui-entrypoint.sh /usr/local/bin/synthpulse-webui
RUN chmod 755 /usr/local/bin/synthpulse-webui && touch /.within_container
LABEL solutions.synthwave.engine.ref=b59086821cb005d2d8c9890d1bff00b0b7fd2291 solutions.synthwave.webui.ref=bebfbc237065afdbe61695afd9b3f3d77dbd4457 solutions.synthwave.profile=pi-base
USER synthpulse
WORKDIR /opt/synthpulse/hermes-webui
RUN python -c "import sys;sys.path.insert(0,'/opt/synthpulse/hermes-agent');from run_agent import AIAgent;import mcp,aiohttp,mnemosyne"
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/synthpulse-webui"]
