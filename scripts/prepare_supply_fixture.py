"""Render isolated shop markup for visual/interaction regression (no live session)."""
import json,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run import app
from app.services.supply_service import CATALOG
with app.test_client() as c:
 html=c.get('/supplies').data.decode()
 main=html[html.index('<main class="supply-shop">'):html.index('</main>',html.index('<main class="supply-shop">'))+7]
 Path(tempfile.gettempdir(),'pait-supply-fixture.json').write_text(json.dumps({'main':main,'catalog':CATALOG},ensure_ascii=False),encoding='utf8')
