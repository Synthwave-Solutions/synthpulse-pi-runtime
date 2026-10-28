#!/usr/bin/env python3
"""Visible browser launcher and lease-aware computer_use bridge for local agents."""
import argparse
import contextlib
import json
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
import uuid

ENGINE = Path(os.environ.get('SYNTHPULSE_ENGINE_DIR', '/opt/synthpulse/hermes-agent'))
PROFILES_HOME = Path(os.environ.get('SYNTHPULSE_PROFILES_HOME', '/home/synthpulse/.synthpulse-engine'))
sys.path.insert(0, str(ENGINE))


def select_profile(profile):
    if profile:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', profile):
            raise ValueError('Invalid bot profile name')
        root = PROFILES_HOME
        home = root if profile == 'default' else root / 'profiles' / profile
    else:
        value = os.environ.get('HERMES_HOME', '').strip()
        if not value:
            raise ValueError('Pass --profile with the current bot name, or inherit its HERMES_HOME')
        home = Path(value).expanduser().resolve()
    home = home.resolve()
    inherited = os.environ.get('HERMES_HOME', '').strip()
    if inherited:
        active = Path(inherited).expanduser().resolve()
        # A named bot must never redirect this helper into another bot's screen.
        # Operator clients without a named bot context retain explicit selection.
        if active.parent == (PROFILES_HOME / 'profiles').resolve() and home != active:
            raise ValueError('Bot Screen profile differs from the active bot; cross-profile launch refused')
    if not (home / 'config.yaml').is_file():
        raise ValueError('Bot profile is not provisioned; no fallback to another bot')
    os.environ['HERMES_HOME'] = str(home)
    from hermes_constants import set_hermes_home_override
    set_hermes_home_override(home)
    # No inherited user desktop or other bot browser override may redirect this launch.
    for name in ('DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'DBUS_SESSION_BUS_ADDRESS',
                 'AGENT_BROWSER_PROFILE', 'AGENT_BROWSER_EXECUTABLE_PATH'):
        os.environ.pop(name, None)
    return home


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def ensure_desktop():
    from tools.bot_desktop import lease, runtime
    lease.assert_agent_may_act()
    state = runtime.start()
    lease.assert_agent_may_act()
    if not state.running:
        raise RuntimeError(state.blocker or 'Bot desktop did not start')
    return state


def local_mesh_args():
    """Pin only this node's verified mesh FQDN; keep TLS hostname validation intact."""
    try:
        result = subprocess.run(['tailscale', 'status', '--json'], capture_output=True,
                                text=True, timeout=5, check=True)
        own = json.loads(result.stdout).get('Self', {})
        name = str(own.get('DNSName', '')).rstrip('.').lower()
        if not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', name):
            return []
        addresses = [ipaddress.ip_address(v) for v in own.get('TailscaleIPs', [])]
        address = next((v for v in addresses if v.version == 4 and v in ipaddress.ip_network('100.64.0.0/10')), None)
        return [f'--host-resolver-rules=MAP {name} {address}'] if address else []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def open_url(url):
    from tools.bot_desktop import browser, lease, runtime
    target = urlsplit(url)
    if target.scheme not in ('https', 'http') or not target.hostname or target.username or target.password:
        raise ValueError('Use an authorized HTTP(S) app URL without embedded credentials')
    # Honor terminal placement. Never launch a host browser beside a sandbox screen.
    lease.assert_agent_may_act()
    if runtime.tool_placement() != 'gateway':
        raise RuntimeError('Use this bot\'s native browser/computer_use tool inside its terminal sandbox')
    state = ensure_desktop()
    launch = browser.dock_launch()
    if not launch:
        raise RuntimeError('No visible Chromium installed for this bot desktop')
    env = runtime.desktop_env()
    if not env.get('DISPLAY') or not env.get('XAUTHORITY'):
        raise RuntimeError('Bot desktop did not publish its display and authentication')
    browser_args = browser.dock_argv(*launch) + local_mesh_args()
    # Serialize launch admission with takeover; do not alter or release the human lease.
    with lease._locked(lease._path(None)):
        admitted = lease.assert_agent_may_act()
        proc = subprocess.Popen(browser_args + ['--start-maximized', '--new-window', url],
                                env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    if lease.get().epoch != admitted.epoch:
        raise lease.HumanHasControl('Control changed during launch; wait for hand back before inspecting')
    return {'ok': True, 'open_requested': True, 'pid': proc.pid,
            'profile': state.profile, 'display': state.display,
            'next': 'Capture and inspect this bot screen to verify the page; launch alone is not proof'}


def approval_callback(output):
    """Transport a native approval request to the supervising interactive agent harness."""
    def request(command, description, **kwargs):
        request_id = uuid.uuid4().hex
        output.write(json.dumps({'approval_required': True, 'request_id': request_id,
                                 'command': command, 'description': description,
                                 'choices': ['once', 'deny']}) + '\n')
        output.flush()
        try:
            response = json.loads(sys.stdin.readline())
            if response.get('request_id') == request_id and response.get('approval') == 'once':
                return 'once'
        except (ValueError, AttributeError):
            pass
        return 'deny'
    return request


def control(approval_bridge=False):
    from tools.computer_use import tool as desktop_tool
    from tools.computer_use.tool import handle_computer_use, release_computer_use_session
    # This bridge returns local screenshot paths to the calling agent's image viewer.
    # Do not route them through the profile's unrelated chat-model/auxiliary provider.
    # Presentation only: dispatch, approvals and takeover fencing stay native.
    desktop_tool._should_route_through_aux_vision = lambda: False
    if approval_bridge:
        # Supported native callback transport, not a policy bypass or permanent grant.
        os.environ['HERMES_INTERACTIVE'] = '1'
        desktop_tool.set_approval_callback(approval_callback(sys.stdout))
    session = 'botscreen-cli-' + uuid.uuid4().hex
    emit({'ok': True, 'ready': True, 'protocol': 'one computer_use JSON object per line; EOF closes only this controller'})
    try:
        for line in sys.stdin:
            try:
                args = json.loads(line)
                if not isinstance(args, dict) or not args.get('action'):
                    raise ValueError('Expected an object with action')
                ensure_desktop()
                # Logs go to stderr; never print inline screenshots or credentials via base64.
                with contextlib.redirect_stdout(sys.stderr):
                    result = handle_computer_use(args, session_id=session)
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except ValueError:
                        result = {'text': result}
                if isinstance(result, dict) and result.get('_multimodal'):
                    result = {'text': result.get('text_summary'), 'meta': result.get('meta', {})}
                if args['action'] == 'list_apps' and isinstance(result, dict) and isinstance(result.get('apps'), list):
                    apps = result['apps']
                    result = {**result, 'apps': [a for a in apps if a.get('windows')],
                              'total_apps': len(apps), 'filter': 'apps with windows on this desktop'}
                    result['count'] = len(result['apps'])
                emit(result)
            except Exception as exc:
                emit(error_result(exc))
    finally:
        release_computer_use_session(session)


def error_result(exc):
    from tools.bot_desktop.lease import HumanHasControl
    return {'ok': False, 'code': 'human_has_control' if isinstance(exc, HumanHasControl) else 'unavailable',
            'error': str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', help='Current authorized SynthPulse bot profile; otherwise inherit HERMES_HOME')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    commands.add_parser('start')
    controller = commands.add_parser('control')
    controller.add_argument('--approval-bridge', action='store_true',
                            help='Forward one-action native approval requests as JSON to the supervising harness')
    commands.add_parser('open').add_argument('url')
    args = parser.parse_args()
    try:
        select_profile(args.profile)
        from tools.bot_desktop import lease, runtime
        if args.command == 'status':
            state = runtime.status()
            current = lease.get()
            emit({'ok': True, 'profile': state.profile, 'running': state.running,
                  'display': state.display, 'placement': state.placement, 'blocker': state.blocker,
                  'holder': current.holder, 'epoch': current.epoch})
        elif args.command == 'start':
            state = ensure_desktop()
            emit({'ok': True, 'profile': state.profile, 'running': state.running, 'display': state.display})
        elif args.command == 'open':
            emit(open_url(args.url))
        else:
            control(args.approval_bridge)
        return 0
    except Exception as exc:
        emit(error_result(exc))
        return 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
