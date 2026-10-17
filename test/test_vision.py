"""Memory-only camera endpoint boundaries; no real camera or saved user frames."""
import io
import unittest
from unittest.mock import Mock
from flask import Flask
from PIL import Image
from app.routes.vision import bp
from app.services.vision_service import VisionEngine, VisionBusy


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY='test-vision-only', TESTING=True, VISION_REMOTE_ENABLED=True)
        self.app.register_blueprint(bp)
        self.engine = Mock()
        self.engine.detect.return_value = {'face': {'faceLandmarks': []}, 'hand': {'landmarks': []}}
        self.app.extensions['vision_engine'] = self.engine
        self.client = self.app.test_client()
        self.token = self.client.get('/api/vision/capabilities').json['token']

    def frame(self, **changes):
        headers = {'Origin': 'http://localhost', 'X-Vision-Token': self.token, 'Content-Type': 'image/jpeg'}
        headers.update(changes.pop('headers', {}))
        return self.client.post('/api/vision/frame' + changes.pop('query', ''), headers=headers,
                                data=changes.pop('data', b'fake-image'), **changes)

    def test_explicit_enable_and_same_session(self):
        self.app.config['VISION_REMOTE_ENABLED'] = False
        self.assertFalse(self.client.get('/api/vision/capabilities').json['enabled'])
        self.assertEqual(self.frame().status_code, 503)
        self.app.config['VISION_REMOTE_ENABLED'] = True
        self.assertEqual(self.frame(headers={'Origin': 'http://evil.test'}).status_code, 403)
        self.assertEqual(self.frame(headers={'Origin': ''}).status_code, 403)
        self.assertEqual(self.frame(headers={'X-Vision-Token': 'wrong'}).status_code, 403)
        other = self.app.test_client()
        self.assertEqual(other.post('/api/vision/frame', data=b'x', headers={
            'Origin': 'http://localhost', 'X-Vision-Token': self.token, 'Content-Type': 'image/jpeg'}).status_code, 403)
        self.engine.detect.assert_not_called()

    def test_size_type_options_and_response(self):
        self.assertEqual(self.frame(headers={'Content-Type': 'text/plain'}).status_code, 415)
        self.assertEqual(self.frame(data=b'x' * (256*1024+1)).status_code, 413)
        self.assertEqual(self.frame(query='?face=bad').status_code, 400)
        self.assertEqual(self.frame(query='?face=0&hands=0').status_code, 400)
        response = self.frame(query='?face=0&hands=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.engine.detect.assert_called_once_with(b'fake-image', False, True)

    def test_failures_are_bounded_and_private(self):
        for exc, status in [(VisionBusy(), 429), (ValueError('private detail'), 400), (RuntimeError('private detail'), 503)]:
            self.engine.detect.side_effect = exc
            response = self.frame()
            self.assertEqual(response.status_code, status)
            self.assertNotIn('private detail', response.get_data(as_text=True))

    def test_engine_rejects_images_before_model_loading_and_never_queues(self):
        engine = VisionEngine('/no-models-needed')
        for raw in [b'bad-image', self.image(641, 480), self.image(640, 481), self.image(10, 10, 'PNG')]:
            with self.assertRaises(ValueError):
                engine.detect(raw)
            self.assertFalse(engine.lock.locked())
        engine.lock.acquire()
        try:
            with self.assertRaises(VisionBusy):
                engine.detect(b'any')
        finally:
            engine.lock.release()

    @staticmethod
    def image(w, h, fmt='JPEG'):
        output = io.BytesIO()
        Image.new('RGB', (w, h)).save(output, format=fmt)
        return output.getvalue()


if __name__ == '__main__':
    unittest.main()
