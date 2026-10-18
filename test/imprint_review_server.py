"""Loopback-only demonstration with a temporary account and DB, no live user writes."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import redirect, session
from app import create_app
from app.config import Config
from app.db import get_db
from app.services import companion_service as memory, pet_imprint_service as imprint, pet_call_service as calls

storage = tempfile.TemporaryDirectory(prefix='pait-imprint-demo-')
class C(Config):
    TESTING = True
    DATABASE_PATH = str(Path(storage.name)/'demo.db')
    SECRET_KEY = 'local-imprint-demo-only'
    DESKTOP_TASK_SCHEDULER_ENABLED = False
    GLM_API_KEY = ''

app = create_app(C)
class DemoLLM:
    def chat(self, *args, **kwargs):
        raise RuntimeError('The review server never calls a paid model')
app.extensions['llm'] = DemoLLM()
with app.app_context():
    db = get_db()
    db.executescript(Path(Config.SCHEMA_PATH).read_text(encoding='utf-8'))
    db.execute("INSERT INTO users(user_name,pwd) VALUES ('imprint-review','not-a-login-password')")
    db.execute("INSERT INTO companion_owners(owner) VALUES ('user:1')")
    db.execute("INSERT INTO companion_memories(owner,pet_id,category,value,confirmed) VALUES ('user:1',1,'pet_name','汤圆习惯演示',1)")
    db.commit()
    for kind,value,quote in [('activity','lively','汤圆活泼好动。'),('vocality','quiet','汤圆不太爱叫。'),('memory','remember','汤圆喜欢在草坪上和主人一起玩耍。')]:
        result=imprint.mutate('user:1',1,dict(revision=memory.settings('user:1')['revision'],kind=kind,value=value,evidence={'type':'owner','quote':quote}))
        imprint.mutate('user:1',1,dict(revision=result['revision'],confirmed=True),result['cards'][0]['id'],'confirm')
    # This is only a proposed expression for the documented play habit.
    imprint.mutate('user:1',1,dict(revision=memory.settings('user:1')['revision'],kind='play',value='play_bow',evidence={'type':'owner','quote':'汤圆喜欢在草坪上和主人一起玩耍；前伏邀玩只是待主人确认的表达方案。'}))
    # Optional real media are decoded locally, left unconfirmed and never committed.
    for filename in os.environ.get('PET_IMPRINT_REFERENCE','').split(os.pathsep):
        if filename:
            try: calls.source('user:1',1,Path(filename).read_bytes())
            except calls.CallError as error: print('Reference extraction:',str(error))

@app.get('/__qa/tangyuan')
def start():
    session['user_id']='imprint-review';session['auth_kind']='user'
    return redirect('/pet-imprint?petId=1')

@app.context_processor
def description():
    return dict(imprint_demo='汤圆习惯演示：使用独立测试账号与标准柴犬动作载体。活动与安静偏好来自主人已提供的描述，专属外形和独特步态仍需审核；待确认音轨不会自动当作汤圆叫声。')

if __name__ == '__main__':
    app.run(host='127.0.0.1',port=int(os.environ.get('PET_IMPRINT_PORT','5094')),debug=False,use_reloader=False)
