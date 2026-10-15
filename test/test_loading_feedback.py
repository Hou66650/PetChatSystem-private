import unittest
from flask import Flask, Response
from app.loading_feedback import install


class LoadingFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, static_folder='../static')
        self.app.config['APP_VERSION'] = 'test-version'
        install(self.app)
        self.app.add_url_rule('/page', endpoint='page', view_func=lambda: '<!doctype html><HEAD lang="zh"><title>岛</title></HEAD><body>内容</body>')
        self.app.add_url_rule('/json', endpoint='json', view_func=lambda: {'ok': True})
        self.app.add_url_rule('/stream', endpoint='stream', view_func=lambda: Response(iter(['<head></head>']), mimetype='text/html'))
        self.app.add_url_rule('/twice', endpoint='twice', view_func=lambda: '<head><link data-pait-loading-assets></head>')
        self.app.add_url_rule('/fragment', endpoint='fragment', view_func=lambda: '<p>片段</p>')
        self.client = self.app.test_client()

    def test_html_loaded_before_application_scripts(self):
        r = self.client.get('/page')
        text = r.get_data(as_text=True)
        self.assertEqual(text.count('glass-loading.js'), 1)
        self.assertIn('glass-loading.css?v=test-version', text)
        self.assertLess(text.index('glass-loading.js'), text.index('<title>'))
        self.assertIn('内容', text)
        self.assertEqual(int(r.headers['Content-Length']), len(r.data))

    def test_api_stream_fragment_and_duplicate_are_untouched(self):
        self.assertEqual(self.client.get('/json').json, {'ok': True})
        self.assertEqual(self.client.get('/stream').data, b'<head></head>')
        self.assertEqual(self.client.get('/twice').data, b'<head><link data-pait-loading-assets></head>')
        self.assertNotIn(b'glass-loading', self.client.get('/fragment').data)
        self.assertEqual(self.client.head('/page').data, b'')


if __name__ == '__main__':
    unittest.main()
