"""Server-side growth assets use isolated owners and the public stage manifest."""
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.db import get_db
from app.services import growth_service as growth, portal_service, growth_asset_service


class GrowthAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        class C(Config):
            TESTING = True
            DATABASE_PATH = str(Path(self.tmp.name) / 'growth-assets.sqlite')
            SECRET_KEY = 'growth-assets-test'
        self.app = create_app(C)
        with self.app.app_context():
            get_db().executescript(Path(Config.SCHEMA_PATH).read_text(encoding='utf-8'))
        self.client = self.app.test_client()
        self.scope = self.client.get('/api/companion').json['scope']
        with self.client.session_transaction() as session:
            self.owner = 'guest:' + session['companion_guest']

    def tearDown(self):
        self.tmp.cleanup()

    def set_age(self, months, pet=3):
        current = self.client.get('/api/growth/' + str(pet)).json
        payload = {
            'mode': 'real', 'name': '旅行阶段宠物', 'personality': 'gentle',
            'birthday': growth.months_after(growth.today(), -months).isoformat(),
            'adopted': growth.today().isoformat(), 'estimated': True, 'likes': '', 'breed': '',
        }
        return self.client.open('/api/growth/' + str(pet), method='PATCH' if current['enrolled'] else 'POST',
                                json=payload, headers={'X-Profile-Scope': self.scope})

    def test_portal_uses_current_stage_and_preserves_unenrolled_pets(self):
        self.assertEqual(self.set_age(3).status_code, 200)
        with self.app.app_context():
            spec = portal_service.pet_spec(self.owner, '3')
            self.assertEqual(spec['model'], '/static/models/pet-growth-v1/cat/tabby-juvenile.glb')
            self.assertEqual(spec['height'], .58)
            self.assertEqual(spec['growthKey'], '3:幼年:tabby')
            self.assertEqual(portal_service.pet_spec(self.owner, '1')['height'], .95)
        self.assertEqual(self.set_age(7).status_code, 200)
        with self.app.app_context():
            self.assertEqual(portal_service.pet_spec(self.owner, '3')['height'], .72)
        self.assertEqual(self.set_age(13).status_code, 200)
        with self.app.app_context():
            spec = portal_service.pet_spec(self.owner, '3')
            self.assertEqual(spec['model'], '/static/models/petchat-cat-v3/cat.glb')
            self.assertEqual(spec['height'], .85)

    def test_dog_stages_use_species_specific_paths_and_heights(self):
        expected = {1: (.64, '/static/models/pet-growth-v1/shiba/default-juvenile.glb'),
                    2: (.72, '/static/models/pet-growth-v1/husky/default-juvenile.glb'),
                    4: (.76, '/static/models/pet-growth-v1/shepherd/default-juvenile.glb')}
        for pet, (height, model) in expected.items():
            self.assertEqual(self.set_age(3, pet).status_code, 200)
            with self.app.app_context():
                spec = portal_service.pet_spec(self.owner, str(pet))
                self.assertEqual(spec['height'], height)
                self.assertEqual(spec['model'], model)
                self.assertEqual(spec['growthKey'], f'{pet}:幼年:default')
            self.assertEqual(self.set_age(7, pet).status_code, 200)

    def test_private_spec_and_other_owner_are_unchanged(self):
        private = {'custom': True, 'model': '/api/pet-studio/task/assets/adapted', 'height': .85}
        with self.app.app_context():
            self.assertEqual(growth_asset_service.apply_stage(self.owner, '3', private), private)
            self.assertEqual(portal_service.pet_spec('guest:someone-else', '3')['height'], .85)


if __name__ == '__main__':
    unittest.main()
