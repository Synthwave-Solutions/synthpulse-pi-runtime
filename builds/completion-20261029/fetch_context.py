#!/usr/bin/env python3
"""Fetch/extract the exact completion context; never installs or starts services."""
import argparse,hashlib,json,os,shutil,tarfile,tempfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LOCK=json.loads((ROOT/'source-lock.json').read_text())
MAX_ARCHIVE=256*1024*1024
MAX_EXTRACTED=512*1024*1024

def sha(path):
 digest=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
 return digest.hexdigest()

def extract(archive,target):
 if sha(archive)!=LOCK['completion']['archive_sha256']:
  raise ValueError('Completion archive SHA256 mismatch')
 with tarfile.open(archive,'r:gz') as stream:
  members=stream.getmembers()
  if len(members)>100 or sum(m.size for m in members)>MAX_EXTRACTED:
   raise ValueError('Completion archive exceeds extraction limits')
  for m in members:
   p=Path(m.name)
   if p.is_absolute() or '..' in p.parts or not(m.isdir() or m.isfile()):
    raise ValueError('Unsafe archive member')
  stream.extractall(target,members=members,filter='data')
 expected=json.loads((ROOT/'payload-sha256.json').read_text())
 if json.loads((target/'payload-sha256.json').read_text())!=expected:
  raise ValueError('Archive manifest differs from source lock')
 for name,digest in expected.items():
  p=target/name
  if not p.is_file() or p.is_symlink() or sha(p)!=digest:
   raise ValueError('Payload differs: '+name)
 # Version-controlled build inputs must be byte-identical to the release.
 for name in ('Dockerfile','configure_stt.py','model-lock.json','runtime-completion.json','smoke.py',
              'ui/apply_source_patch.py','ui/manifest.json','ui/targeted-changes.patch'):
  if sha(ROOT/name)!=expected[name]:raise ValueError('Tracked source changed: '+name)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--archive',type=Path,help='Use a local archive instead of downloading')
 args=parser.parse_args()
 if args.output.exists():raise ValueError('Output already exists; choose a fresh directory')
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.completion-fetch-',dir=args.output.parent) as scratch:
  temp=Path(scratch);archive=args.archive
  if archive is None:
   archive=temp/'completion.tar.gz';total=0
   with urllib.request.urlopen(LOCK['completion']['archive_url'],timeout=120) as response,archive.open('wb') as stream:
    while block:=response.read(1024*1024):
     total+=len(block)
     if total>MAX_ARCHIVE:raise ValueError('Download exceeds size limit')
     stream.write(block)
  context=temp/'context';extract(archive,context)
  context.rename(args.output)
 print(json.dumps({'context':str(args.output),'revision':LOCK['completion']['revision'],'verified':True}))

if __name__=='__main__':main()
