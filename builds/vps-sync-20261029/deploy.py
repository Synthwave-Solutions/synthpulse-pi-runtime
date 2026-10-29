#!/usr/bin/env python3
"""Deploy a built image on AddContract after preserving the current state."""
import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    if os.geteuid() != 0 or socket.gethostname() != 'addcontract-pi':
        raise SystemExit('Run as root on addcontract-pi only')
    image = sys.argv[1]
    inspection = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
    if inspection['Architecture'] != 'arm64':
        raise SystemExit('ARM64 image required')
    lock = json.loads(Path(__file__).with_name('source-lock.json').read_text())
    if inspection['Config']['Labels'].get('solutions.synthwave.webui.ref') != lock['webui_commit']:
        raise SystemExit('Image/source lock mismatch')
    root = Path('/opt/synthpulse/iuvenis-pi')
    compose = root / 'compose.json'
    original = compose.read_bytes()
    config = json.loads(original)
    for service in ('webui', 'gateway'):
        if config['services'][service]['image'] != lock['base_image']:
            raise SystemExit('Existing deployment changed; compare before upgrading')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/root/recovery-20261029') / ('vps-sync-' + stamp)
    backup.mkdir(mode=0o700)
    (backup / 'compose.json').write_bytes(original)
    os.chmod(backup / 'compose.json', 0o600)
    command = ['docker', 'compose', '-f', str(compose), '--project-directory', str(root)]
    try:
        run(*command, 'stop', '-t', '60', 'webui', 'gateway')
        # Both writers are stopped. Keep state, sessions, policy and customer env.
        run('tar', '-czf', str(backup / 'customer-state.tar.gz'), '-C', str(root),
            'state', 'runtime.env', 'policy.yaml', 'start.sh')
        os.chmod(backup / 'customer-state.tar.gz', 0o600)
        run('tar', '-tzf', str(backup / 'customer-state.tar.gz'), stdout=subprocess.DEVNULL)
        for service in ('webui', 'gateway'):
            config['services'][service]['image'] = inspection['Id']
        temporary = compose.with_suffix('.json.next')
        temporary.write_text(json.dumps(config, indent=2) + '\n')
        os.chmod(temporary, compose.stat().st_mode & 0o777)
        temporary.replace(compose)
        run(*command, 'up', '-d', '--no-deps', 'webui', 'gateway')
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            states = json.loads(subprocess.check_output([
                'docker', 'inspect', 'iuvenis-pi-webui-1', 'iuvenis-pi-gateway-1']))
            if all(s['State'].get('Health', {}).get('Status') == 'healthy' for s in states):
                result = {'image': inspection['Id'], 'backup': str(backup), 'healthy': True,
                          'webui_commit': lock['webui_commit'], 'vps_webui_commit': lock['vps_webui_commit']}
                (backup / 'deployment.json').write_text(json.dumps(result, indent=2) + '\n')
                print(json.dumps(result))
                return
            time.sleep(3)
        raise RuntimeError('New services did not become healthy')
    except BaseException:
        compose.write_bytes(original)
        run(*command, 'up', '-d', '--no-deps', 'webui', 'gateway')
        # Preserve both post-upgrade and backup state; never overwrite data on failure.
        print('Previous image restored; backup: ' + str(backup), file=sys.stderr)
        raise


if __name__ == '__main__':
    main()
