"""Disposable loopback fixture, never uses the user's database or LLM account."""
import sys,tempfile,json,io,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import session,redirect
from app import create_app
from app.config import Config
from app.db import get_db
root=tempfile.TemporaryDirectory()
class C(Config):
    TESTING=True
    TEMPLATES_AUTO_RELOAD=True
    SECRET_KEY='desktop-transfer-test'
    DATABASE_PATH=str(Path(root.name)/'test.db')
    GLM_API_KEY='fixture-only-never-sent'
    DESKTOP_AGENT_ENABLED=True
app=create_app(C)
class LocalPlan:
    def plan_once(self,*args,**kwargs):return '{"visitor":"walk","host":"walk"}'
    def chat(self,*args,**kwargs):return json.dumps({'reply':'我在桌面陪你。','actions':[],'memories':[]})
app.extensions['llm']=LocalPlan()
from app.services import pet_voice_service
def local_speech(text,voice):
    buf=io.BytesIO()
    with wave.open(buf,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*16000)
    return buf.getvalue()
pet_voice_service.synthesize=local_speech
with app.app_context():
    db=get_db();db.executescript(Path(Config.SCHEMA_PATH).read_text(encoding='utf-8'))
    db.execute("INSERT INTO users(user_name,pwd) VALUES ('desktop-test','unused')")
    for item,slot in [('moss-bow','neck'),('daisy','head')]:
        db.execute('INSERT INTO pet_wardrobe_owned VALUES (?,?,0)',('user:1',item))
        db.execute('INSERT INTO pet_wardrobe_equipped VALUES (?,?,?,?)',('user:1',1,slot,item))
    db.commit()
@app.get('/__qa/login')
def login():
    session['user_id']='desktop-test';session['auth_kind']='user';return redirect('/den?pet=1')
if __name__=='__main__':app.run(host='127.0.0.1',port=5091,debug=False,use_reloader=False)
