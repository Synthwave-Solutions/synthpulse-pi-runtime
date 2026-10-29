"""Real local consolidation on a NEW synthetic bank only; never a production path.
Caller must supply an empty disposable directory and isolated HOME/config env.
Embeddings/LLM are disabled for this bounded fallback-consolidation proof.
"""
import json,sys
from pathlib import Path
from datetime import datetime,timedelta
from importlib.metadata import version
p=Path(sys.argv[1]);assert not p.exists(),'Test bank must not already exist'
p.parent.mkdir(parents=True,exist_ok=True)
from mnemosyne import Mnemosyne
from mnemosyne.core.beam import WORKING_MEMORY_TTL_HOURS
m=Mnemosyne(db_path=p,session_id='isolated-consolidation-test')
m.agent_context='cron'
for note in ['Test project uses a green sample folder.','Test project review is on Tuesday.','Test project owner prefers a concise recap.']:
 m.remember(note,source='test',importance=0.7)
cutoff=(datetime.now()-timedelta(hours=WORKING_MEMORY_TTL_HOURS+1)).isoformat()
m.conn.execute('UPDATE working_memory SET timestamp=?',(cutoff,));m.conn.commit()
result=m.sleep_all_sessions(force=False)
assert result['items_consolidated']>=3,result
assert m.conn.execute('SELECT COUNT(*) FROM episodic_memory').fetchone()[0]>0
assert m.conn.execute('SELECT COUNT(*) FROM consolidation_log').fetchone()[0]>0
print(json.dumps({'mnemosyne_version':version('mnemosyne-memory'),'force':False,'items_consolidated':result['items_consolidated'],'summaries_created':result['summaries_created'],'llm_used':result['llm_used'],'embedding_tested':False}))
