"""Loopback-only browser review fixture. Temporary DB, two test-only accounts."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import session, redirect
from app import create_app
from app.config import Config
from app.db import get_db
root=tempfile.TemporaryDirectory()
class C(Config):
    TESTING=True
    SECRET_KEY='isolated-park-review'
    DATABASE_PATH=str(Path(root.name)/'review.db')
app=create_app(C)
with app.app_context():
    db=get_db();db.executescript(Path(Config.SCHEMA_PATH).read_text(encoding='utf-8'))
    db.executemany('INSERT INTO users(user_name,pwd) VALUES (?,?)',[('park-a','unused'),('park-b','unused')]);db.commit()
@app.get('/__qa/<name>')
def qa(name):
    if name not in ('park-a','park-b'):return '',404
    session['user_id']=name;session['auth_kind']='user';return redirect('/park')
if __name__=='__main__':
    app.run(host='127.0.0.1',port=5088,debug=False,use_reloader=False)
