"""Render a public component fixture with a fresh isolated database (never live data)."""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import render_template
from app import create_app
from app.config import Config
from app.services import farm_service as farm
with tempfile.TemporaryDirectory() as folder:
    class FixtureConfig(Config):
        TESTING=True
        DATABASE_PATH=str(Path(folder)/'fixture.db')
        SECRET_KEY='garden-component-fixture'
    app=create_app(FixtureConfig)
    with app.test_request_context():
        html=render_template('_farm.html',farm_layout=farm.LAYOUT,app_version='fixture')
        data=farm.state('user:fixture')
        Path(tempfile.gettempdir(),'pait-farm-fixture.json').write_text(json.dumps(dict(html=html,state=data,layout=farm.LAYOUT),ensure_ascii=False),encoding='utf-8')
print('Prepared isolated farm component fixture')
