#!/bin/sh
# ============================================================================
# SynthPulse WebUI container entrypoint.
#
# Three jobs, in this order:
#   1. make the persisted tree exist (state dir, engine home, agent symlink)
#   2. check the two preconditions that otherwise fail SILENTLY at run time
#      (engine importable, governance policy present) and say so loudly
#   3. exec server.py with the ENGINE interpreter
#
# Deliberately NOT bootstrap.py: that script creates/repairs venvs, detaches,
# probes and opens a browser, none of which a container may do. Code lives in
# the image, state lives on the volume.
#
# Preconditions are configurable so a client deployment can choose between
# "crash loudly" and "run degraded":
#   SP_WEBUI_REQUIRE_ENGINE=1      (default) exit 1 when the engine cannot be
#                                  imported. A WebUI that cannot import the
#                                  engine serves pages but fails every turn.
#   SP_WEBUI_REQUIRE_GOVERNANCE=0  (default) warn when the governance policy is
#                                  missing; set 1 to refuse to start without it
#                                  (recommended once governance is in enforce).
# ============================================================================
set -eu

# ── SP_WEBUI_* is the product-facing name ───────────────────────────────────
# docker-compose.yml maps them onto the HERMES_WEBUI_* names the server reads.
# Do the same mapping here so the image is correct on its own too (plain
# `docker run`, a swarm stack, a k8s manifest): without it a deployment that
# sets SP_WEBUI_PASSWORD would come up with NO authentication at all. A
# non-empty SP_WEBUI_* wins, because it is the value a client configured.
sp_map(){ # $1 = SP_ name, $2 = HERMES_ name
  eval "_v=\${$1:-}"
  [ -n "${_v:-}" ] || return 0
  eval "export $2=\"\$_v\""
}
for _s in PASSWORD PASSWORD_IDENTITY REQUIRE_SSO_FIRST \
          OIDC_ISSUER OIDC_CLIENT_ID OIDC_CLIENT_SECRET OIDC_REDIRECT_URI \
          OIDC_SCOPES OIDC_ALLOW_CLAIM OIDC_ALLOW_VALUES \
          DEFAULT_HIDDEN_TABS USER_ISOLATION ADMIN_SEES_ALL \
          ALLOWED_ORIGINS TRUSTED_PROXY_CIDRS STATE_DIR; do
  sp_map "SP_WEBUI_$_s" "HERMES_WEBUI_$_s"
done
sp_map SP_WEBUI_ENGINE_HOME     HERMES_HOME
sp_map SP_WEBUI_GOVERNANCE_FILE HERMES_WEBUI_GOVERNANCE_POLICY
unset _s _v

PY="${HERMES_WEBUI_PYTHON:-/opt/synthpulse/hermes-agent/venv/bin/python}"
APP="${SP_WEBUI_DIR:-/opt/synthpulse/hermes-webui}"
ENGINE_DIR="${HERMES_WEBUI_AGENT_DIR:-/opt/synthpulse/hermes-agent}"
ENGINE_HOME="${HERMES_HOME:-/home/synthpulse/.synthpulse-engine}"
STATE_DIR="${HERMES_WEBUI_STATE_DIR:-$ENGINE_HOME/webui}"
POLICY="${HERMES_WEBUI_GOVERNANCE_POLICY:-$ENGINE_HOME/dashboard-governance.yaml}"
REQUIRE_ENGINE="${SP_WEBUI_REQUIRE_ENGINE:-1}"
REQUIRE_GOVERNANCE="${SP_WEBUI_REQUIRE_GOVERNANCE:-0}"

say(){ printf '[webui] %s\n' "$*"; }
die(){ printf '[webui] FATAL: %s\n' "$*" >&2; exit 1; }

[ -f "$APP/server.py" ] || die "no WebUI source at $APP/server.py (broken image)"
[ -x "$PY" ] || die "engine interpreter not found at $PY (broken image)"

# ── 1. persisted tree ───────────────────────────────────────────────────────
mkdir -p "$STATE_DIR" "$ENGINE_HOME/profiles" || \
  die "cannot create $STATE_DIR (is the state volume writable by uid $(id -u)?)"

# Several engine-side modules expect the checkout at <engine home>/hermes-agent.
# The code itself stays in the image; this is only a pointer.
[ -e "$ENGINE_HOME/hermes-agent" ] || ln -sfn "$ENGINE_DIR" "$ENGINE_HOME/hermes-agent" 2>/dev/null || true

# ── 2. preconditions that otherwise fail silently ───────────────────────────
# The engine is an IN-PROCESS import, not an HTTP dependency: if this probe
# fails, the UI loads and every chat turn dies with "AIAgent not available".
if ! "$PY" - <<'PROBE' >/dev/null 2>&1
import os, sys
sys.path.append(os.environ.get("HERMES_WEBUI_AGENT_DIR", "/opt/synthpulse/hermes-agent"))
import yaml  # noqa: F401
from run_agent import AIAgent  # noqa: F401
PROBE
then
  say "the engine is NOT importable with $PY"
  say "  chat needs 'import yaml; from run_agent import AIAgent' to succeed."
  say "  check that HERMES_WEBUI_AGENT_DIR ($ENGINE_DIR) holds the engine and"
  say "  that its venv is the interpreter above (HERMES_WEBUI_PYTHON)."
  case "$REQUIRE_ENGINE" in
    1|true|yes|on) die "refusing to start chat-less (set SP_WEBUI_REQUIRE_ENGINE=0 to override)" ;;
    *) say "  continuing anyway (SP_WEBUI_REQUIRE_ENGINE=$REQUIRE_ENGINE)" ;;
  esac
else
  say "engine import ok ($ENGINE_DIR)"
fi

# A missing policy file does not raise: the governance layer falls back to
# mode "off", so an enforcing deployment silently stops enforcing. Never let
# that happen quietly.
if [ ! -f "$POLICY" ]; then
  say "governance policy NOT found at $POLICY"
  say "  role/group/grant enforcement will be INACTIVE until it exists."
  say "  render it from client.yaml and apply the chain in modules/ops/governance/."
  case "$REQUIRE_GOVERNANCE" in
    1|true|yes|on) die "refusing to start ungoverned (SP_WEBUI_REQUIRE_GOVERNANCE=1)" ;;
  esac
else
  say "governance policy: $POLICY"
fi

# ── Auth: OIDC first, password as the break-glass ───────────────────────────
# SP_WEBUI_SSO_ENABLED comes from client.yaml (webui.sso.enabled). 0 is a real
# kill switch: it drops the OIDC configuration even when an issuer is still
# present in the environment, leaving password-only login.
case "${SP_WEBUI_SSO_ENABLED:-1}" in
  0|false|no|off)
    unset HERMES_WEBUI_OIDC_ISSUER HERMES_WEBUI_OIDC_CLIENT_ID \
          HERMES_WEBUI_OIDC_CLIENT_SECRET HERMES_WEBUI_OIDC_REDIRECT_URI
    say "SSO disabled by client config: password login only"
    ;;
esac

# ── The fail-open hole, closed here ─────────────────────────────────────────
# The upstream auth gate is OPT-IN: check_auth() returns True immediately when
# no provider is registered, and no provider is registered when password,
# passkeys and OIDC are all unset. So "no credentials configured" does NOT mean
# "nobody can sign in", it means EVERY route is served unauthenticated. With
# profiles webui+ingress the Caddyfile publishes webui.{SP_DOMAIN} with TLS, so
# the result is a public, unauthenticated interface over the client's filesystem
# and agent.
#
# A warning is not a control, so this generates an EPHEMERAL break-glass
# password and arms the gate, exactly as the dashboard-auth sidecar does for the
# engine dashboard. The deployment still boots; it boots CLOSED.
#
#   SP_WEBUI_ALLOW_NO_AUTH=1  serve with no auth provider anyway. Only for a
#                             deployment that terminates authentication in front
#                             of this container (its own proxy) AND never
#                             publishes it directly.
if [ -z "${HERMES_WEBUI_OIDC_ISSUER:-}" ] && [ -z "${HERMES_WEBUI_PASSWORD:-}" ]; then
  _bind="${HERMES_WEBUI_HOST:-0.0.0.0}"
  case "$_bind" in
    127.0.0.1|::1|localhost) _loopback=1 ;;
    *) _loopback=0 ;;
  esac
  case "${SP_WEBUI_ALLOW_NO_AUTH:-0}" in
    1|true|yes|on) _allow_open=1 ;;
    *) _allow_open=0 ;;
  esac
  if [ "$_allow_open" = 1 ]; then
    say "WARNING: no auth provider AND SP_WEBUI_ALLOW_NO_AUTH=1: every route is"
    say "  served UNAUTHENTICATED on $_bind. Only safe behind your own auth proxy."
  elif [ "$_loopback" = 1 ]; then
    say "WARNING: no OIDC issuer and no fallback password configured."
    say "  the bind is loopback ($_bind) so this is not reachable off-container,"
    say "  but every route is unauthenticated. Set SP_WEBUI_PASSWORD before"
    say "  changing the bind or putting this behind a hostname."
  else
    HERMES_WEBUI_PASSWORD="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || \
      "$PY" -c 'import secrets;print(secrets.token_hex(12))')"
    export HERMES_WEBUI_PASSWORD
    say "WARNING: no OIDC issuer and no SP_WEBUI_PASSWORD, and the bind is"
    say "  $_bind (reachable). Refusing to serve an OPEN interface: generated an"
    say "  EPHEMERAL break-glass password. It changes on every restart, so set"
    say "  SP_WEBUI_PASSWORD in client.env to keep one stable credential"
    say "  (modules/secrets/ensure-secrets.py generates it for you)."
    say "  password=$HERMES_WEBUI_PASSWORD"
  fi
  unset _bind _loopback _allow_open
fi

say "listening on ${HERMES_WEBUI_HOST:-0.0.0.0}:${HERMES_WEBUI_PORT:-8787} (state: $STATE_DIR)"

# ── 3. serve ────────────────────────────────────────────────────────────────
cd "$APP"
exec "$PY" server.py "$@"
