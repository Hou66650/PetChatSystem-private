"""Local Windows service: client-branch code, original account store, no DB copy.
Use --fixture for isolated verification; it never opens the production database.
"""
import argparse
import os
from pathlib import Path
import runpy
import sys

root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root))
parser=argparse.ArgumentParser()
parser.add_argument('--source-root',type=Path,default=Path('D:/PetChatSystem'))
parser.add_argument('--port',type=int,default=5012)
parser.add_argument('--fixture',action='store_true')
args=parser.parse_args()

if args.fixture:
    os.environ['GLM_API_KEY']=''
    os.environ['DATABASE']=str(root/'native/windows/Saved/Qualification/native-fixture.db')
    from app.config import Config
    Config.TESTING=True
    Config.NATIVE_FIXTURE=True
else:
    # Load settings directly into this server process; never print/export keys.
    config_file=args.source_root/'app/config.py'
    if not config_file.is_file():raise SystemExit('Original server configuration was not found')
    Config=runpy.run_path(str(config_file))['Config']
    if not Path(Config.DATABASE_PATH).is_file():raise SystemExit('Original database missing; will not create an empty replacement')
from app import create_app
if args.fixture:
    from unittest.mock import patch
    with patch('app.GLMClient'):
        app=create_app(Config)
else:
    app=create_app(Config)

@app.before_request
def native_only():
    from flask import request,jsonify
    if not request.path.startswith('/api/native/v1/'):
        return jsonify(error='This listener only serves the native API'),404

if args.fixture:
    from app.db import get_db,init_db
    from werkzeug.security import generate_password_hash
    import json,time
    with app.app_context():
        init_db(); db=get_db()
        with db:
            for name in ('native-check-a','native-check-b'):
                db.execute('INSERT OR IGNORE INTO users(user_name,pwd) VALUES (?,?)',(name,generate_password_hash('native-isolated-check')))
            # Seed only this explicitly isolated fixture's botanical visual examples.
            user=db.execute('SELECT user_id FROM users WHERE user_name=?',('native-check-a',)).fetchone()[0]
            for bed,species,age in [('bed-1','rose',20),('bed-2','tulip',48),('bed-3','cosmos',9)]:
                db.execute('INSERT OR IGNORE INTO farm_plants(owner,bed,id,species,planted) VALUES (?,?,?,?,?)',('user:'+str(user),bed,'fixture-'+bed,species,time.time()-age*3600))
    class FixtureModel:
        def chat(self,*a,**kw):return json.dumps({'reply':'这是隔离检查中的宠物回复。','actions':[],'memories':[]})
    app.extensions['llm']=FixtureModel()

app.run(host='127.0.0.1',port=args.port,debug=False,use_reloader=False,threaded=True)
