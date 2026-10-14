"""Prepare public UI and mock catalog for the isolated Electron market test."""
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.services.cat_market_service import CATALOG
app=create_app()
with app.test_client() as client:
 response=client.get('/cat-market');assert response.status_code==200
 Path(tempfile.gettempdir(),'pait-market-fixture.html').write_bytes(response.data)
Path(tempfile.gettempdir(),'pait-market-fixture.json').write_text(json.dumps(dict(catalog=CATALOG,active='tabby',balance=160,owned=['tabby'],guest=False,dailyClaimed=False,ledger=[],scope='fixture')),encoding='utf-8')
