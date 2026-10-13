"""Isolated demo server: real LLM, temporary database, no production user records."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE']='/tmp/petchat-companion-validation.db'
from app import create_app
from app.db import get_db
from app.config import Config
app=create_app()
with app.app_context():
    get_db().executescript(Path(Config.SCHEMA_PATH).read_text(encoding='utf-8'))
app.run(host='0.0.0.0',port=5003,use_reloader=False)
