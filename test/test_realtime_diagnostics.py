import unittest
from unittest.mock import patch
from flask import Flask
from app.routes import realtime


class RealtimeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__);self.app.register_blueprint(realtime.bp)
        self.client=self.app.test_client();realtime._diagnostic_hits.clear()
        self.metadata=dict(petId=3,stage='provider',code='downstream_reconnect_exceeded',status=0)

    def post(self,**overrides):
        return self.client.post('/api/realtime/diagnostics',json={**self.metadata,**overrides})

    def test_only_allowlisted_metadata_reaches_log(self):
        with patch.object(self.app.logger,'warning') as log:
            self.assertEqual(self.post(token='SECRET',transcript='PRIVATE',message='PRIVATE').status_code,200)
        self.assertNotIn('SECRET',str(log.call_args));self.assertNotIn('PRIVATE',str(log.call_args))
        self.assertIn('downstream_reconnect_exceeded',str(log.call_args))

    def test_malformed_oversized_and_cross_origin_rejected(self):
        for changes in [dict(petId=True),dict(petId=9),dict(code='line\nbreak'),dict(code='x'*65),dict(stage='other'),dict(status=True)]:
            self.assertEqual(self.post(**changes).status_code,400)
        self.assertEqual(self.post(ignored='x'*2100).status_code,413)
        self.assertEqual(self.client.post('/api/realtime/diagnostics',json=self.metadata,headers={'Origin':'https://other.example'}).status_code,403)

    def test_report_rate_limit_separate_from_session(self):
        with patch.object(self.app.logger,'warning'):
            for _ in range(30):self.assertEqual(self.post().status_code,200)
            self.assertEqual(self.post().status_code,429)
        self.assertEqual(len(realtime._diagnostic_hits['127.0.0.1']),30)


if __name__=='__main__':unittest.main()
