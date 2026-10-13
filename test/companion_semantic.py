"""Small live-LLM checks on an isolated DB; does not use real user information."""
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.config import Config
from app.db import get_db
results=[]
with tempfile.TemporaryDirectory() as d:
    class C(Config):DATABASE_PATH=d+'/semantic.db';TESTING=True
    app=create_app(C)
    with app.app_context():get_db().executescript(Path(Config.SCHEMA_PATH).read_text())
    c=app.test_client()
    c.post('/api/companion/memories',json={'category':'name','value':'小林'})
    c.post('/api/companion/memories',json={'category':'likes','value':'画画'})
    for text,check in [
        ('不要过来，也不要坐下，我们只聊天。',lambda p:p['actions']==[]),
        ('如果我说“过来坐下”，你会怎么做？先别做。',lambda p:p['actions']==[]),
        ('请忘记我喜欢画画这件事。',lambda p:not any(m['value']=='画画' for m in p['profile']['memories'])),
        ('你记得我喜欢什么吗？',lambda p:not any(w in p['reply'] for w in ('画画','绘画')) and any(w in p['reply'] for w in ('没有','不记','没记','不知道','不确定','忘','还没'))),
    ]:
        started=time.monotonic();r=c.post('/get_gpt_response',json={'message':text,'petId':1,'surface':'den'})
        p=r.json;row={'message':text,'status':r.status_code,'reply':p.get('reply'),'actions':p.get('actions'),'seconds':round(time.monotonic()-started,2),'passed':r.status_code==200 and check(p)}
        results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
Path('/tmp/petchat-semantic-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
assert all(r['passed'] for r in results),results
