"""Offline current-image API + actual fallback-consolidation smoke; disposable data only."""
import contextlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=['/opt/synthpulse/hermes-webui','/opt/synthpulse/hermes-agent','/test']
import memdash_harness as H
class MP:
 def __init__(self):self.stack=contextlib.ExitStack()
 def setattr(self,obj,name,value):self.stack.enter_context(patch.object(obj,name,value))
 def setenv(self,name,value):self.stack.enter_context(patch.dict(os.environ,{name:value}))
 def delenv(self,name,raising=False):
  env=dict(os.environ);env.pop(name,None);self.stack.enter_context(patch.dict(os.environ,env,clear=True))
with tempfile.TemporaryDirectory(prefix='runtime-completion-memory-') as tmp:
 root=Path(tmp);mp=MP();e=H.Env(mp,root,backend='local_personal')
 try:
  from api import config,personal_context,memdash_backend
  mp.setattr(config,'STATE_DIR',e.state)
  e.set_policy(H.hq_policy(installation={'kind':'client','name':'Synthetic test'}))
  bank=personal_context.home({'email':H.ADA})/'mnemosyne/private.db'
  isolated=root/'isolated';isolated.mkdir()
  env={'PATH':os.environ['PATH'],'HERMES_HOME':str(isolated/'hermes'),'MNEMOSYNE_DATA_DIR':str(isolated/'data'),
   'MNEMOSYNE_LLM_ENABLED':'false','MNEMOSYNE_HOST_LLM_ENABLED':'false','MNEMOSYNE_NO_EMBEDDINGS':'1','MNEMOSYNE_SKIP_EMBEDDINGS':'1','HF_HUB_OFFLINE':'1'}
  result=subprocess.run([sys.executable,'/test/consolidate_test_bank.py',str(bank)],env=env,text=True,capture_output=True,timeout=60)
  assert result.returncode==0,result.stderr
  proof=json.loads(result.stdout.splitlines()[-1])
  banks=e.banks();assert banks['available'] and len(banks['stores'])==1,banks
  consolidated=e.view('me','consolidations');assert consolidated.status==200,consolidated.body
  assert any(row.get('items_consolidated',0)>=3 for row in consolidated.body['items']),consolidated.body
  episodic=e.view('me','memories',kind='episodic');assert episodic.status==200,episodic.body
  assert 'green sample folder' in str(episodic.body)
  print(json.dumps({'offline':True,'api_contract':'passed','real_consolidation':proof,'episodic_view':'passed'}))
 finally:
  shared=memdash_backend.LocalPersonalBackend._shared
  if shared:shared.reader.close()
  e.close();mp.stack.close()
