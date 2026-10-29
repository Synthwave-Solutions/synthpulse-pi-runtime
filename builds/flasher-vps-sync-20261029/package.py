#!/usr/bin/env python3
"""Recreate the four verified source-context inputs without publishing anything."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
FILES = ('Dockerfile', 'webui.tar', 'source-lock.json', 'runtime-hashes.json')


def package(output, source=None):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Output exists; immutable releases must not be overwritten')
    lock=json.loads((ROOT/'source-lock.json').read_text())
    expected=json.loads((ROOT/'runtime-hashes.json').read_text())
    commit=lock['webui_commit']
    with tempfile.TemporaryDirectory(prefix='synthpulse-source-package-') as temporary:
        work=Path(temporary)
        if source:
            repo=Path(source).resolve()
        else:
            repo=work/'source.git'
            subprocess.run(['git','init','--bare',str(repo)],check=True,stdout=subprocess.DEVNULL)
            # Uses existing Git credentials; GH_TOKEN can be supplied with gh's helper.
            auth=['-c','credential.helper=','-c','credential.helper=!gh auth git-credential'] if shutil.which('gh') else []
            subprocess.run(['git',*auth,'-C',str(repo),'fetch','--depth=1',
                            'https://github.com/'+lock['webui_repository']+'.git',commit],check=True)
        resolved=subprocess.check_output(['git','-C',str(repo),'rev-parse',commit+'^{commit}'],text=True).strip()
        if resolved!=commit:raise ValueError('Resolved source commit differs from pin')
        subprocess.run(['git','-C',str(repo),'archive','--format=tar','--output',str(work/'webui.tar'),commit],check=True)
        with tarfile.open(work/'webui.tar','r:') as source_tar:
            members=source_tar.getmembers()
            if any(not (m.isfile() or m.isdir()) for m in members):raise ValueError('Unexpected source archive link')
            actual={m.name:hashlib.sha256(source_tar.extractfile(m).read()).hexdigest() for m in members if m.isfile()}
        if actual!=expected:raise ValueError('Source differs from reviewed complete file manifest')
        for name in FILES:
            if name!='webui.tar':shutil.copyfile(ROOT/name,work/name)
        # Fixed metadata makes future rebuilds deterministic. Historical release used
        # filesystem timestamps, so this recreated gzip has a new SHA; never replace it.
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('xb') as raw:
            with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
                with tarfile.open(fileobj=compressed,mode='w',format=tarfile.PAX_FORMAT) as tar:
                    for name in FILES:
                        info=tarfile.TarInfo(name);info.size=(work/name).stat().st_size
                        info.mode=0o644;info.mtime=0
                        with (work/name).open('rb') as handle:tar.addfile(info,handle)
        print(json.dumps({'archive':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
                          'source_files':len(actual),'webui_commit':commit}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,help='New archive path; existing output is refused')
    parser.add_argument('--source',help='Optional local Git checkout containing the pinned commit')
    args=parser.parse_args()
    package(args.output,args.source)
