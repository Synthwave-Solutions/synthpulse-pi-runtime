#!/usr/bin/env python3
"""Apply only reviewed current-runtime deltas, refusing unexpected file versions."""
import argparse,hashlib,json,os,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('webui_root',type=Path);a=p.parse_args()
here=Path(__file__).resolve().parent
manifest=json.loads((here/'manifest.json').read_text())
pending=[]
for relative,hashes in manifest['files'].items():
 dest=a.webui_root/relative;src=here/'patched'/relative
 if dest.is_symlink() or any(x.is_symlink() for x in dest.parents):raise SystemExit('Refusing symlink')
 digest=hashlib.sha256(dest.read_bytes()).hexdigest()
 if digest not in hashes.values():raise SystemExit('Unexpected source version: '+relative)
 if hashlib.sha256(src.read_bytes()).hexdigest()!=hashes['after_sha256']:raise SystemExit('Patch payload changed: '+relative)
 if digest!=hashes['after_sha256']:pending.append((dest,src))
for dest,src in pending:
 meta=dest.stat();fd,tmp=tempfile.mkstemp(dir=dest.parent,prefix='.'+dest.name)
 try:
  with os.fdopen(fd,'wb') as stream:stream.write(src.read_bytes());stream.flush();os.fsync(stream.fileno())
  os.chmod(tmp,meta.st_mode & 0o777)
  if os.geteuid()==0:os.chown(tmp,meta.st_uid,meta.st_gid)
  os.replace(tmp,dest)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
print(json.dumps({'files_updated':len(pending),'base_commit':manifest['base_commit']}))
