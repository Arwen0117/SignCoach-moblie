import json
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient
from asl_realtime import api_server, scoring
from asl_realtime.preprocess import prepare_sequence
from asl_realtime.attempt_store import AttemptStore
from asl_realtime.diagnostics import diagnostics


class DemoContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'attempts.sqlite3'
        self.web = Path(self.temp.name) / 'web'
        (self.web / 'assets').mkdir(parents=True)
        (self.web / 'index.html').write_text('<html>Demo</html>')
        self.detector = Mock()
        self.detector.process.return_value = SimpleNamespace()
        module = Mock()
        module.Holistic.return_value = self.detector
        self.reference = Mock()
        self.reference.search_target.return_value = dict(target_similarity=.95, best_other_similarity=.8, similarity_margin=.15, best_other_word='BLUE')
        with patch.object(api_server, 'get_holistic_module', return_value=module):
            self.client = TestClient(api_server.build_app(self.reference, self.db, web_dir=self.web))
        self.addCleanup(self.client.close)
        self.raw = cv2.imencode('.jpg', np.zeros((16, 16, 3), np.uint8))[1].tobytes()
        self.attempt = str(uuid.uuid4())

    def post(self, final=False, target='APPLE', raw=None):
        return self.client.post('/api/practice/frame', params=dict(attempt_id=self.attempt, target_word=target, final=final), content=self.raw if raw is None else raw, headers={'Content-Type':'image/jpeg'})

    def test_health_labels_and_validation(self):
        self.assertEqual({'ok': True, 'model_version':'manual-baseline-v1'}, self.client.get('/api/health').json())
        self.assertEqual(30, len(self.client.get('/api/labels').json()['labels']))
        self.assertEqual(422, self.post(target='MOTHER').status_code)
        self.assertEqual(400, self.post(raw=b'broken').status_code)
        self.assertEqual(422, self.client.get('/api/attempts?limit=101').status_code)

    def test_rerecord_early_exit_and_persistence_feedback(self):
        with patch.object(scoring, 'manual_baseline_score', wraps=scoring.manual_baseline_score) as score:
            for _ in range(6):
                response = self.post()
                self.assertEqual((204, b''), (response.status_code, response.content))
            response = self.post(True)
            self.assertEqual(200, response.status_code)
            result = response.json()
            self.assertEqual('rerecord', result['decision'])
            self.assertIsNone(result['score'])
            self.assertIsNone(result['nearest_confusion'])
            self.assertLessEqual(len(result['diagnostics']), 2)
            self.reference.search_target.assert_not_called()
            score.assert_not_called()
        self.assertEqual(7, self.detector.process.call_count)
        self.assertEqual(result, self.post(True).json())
        self.assertEqual(7, self.detector.process.call_count)
        self.assertEqual(409, self.post(True, target='BLUE').status_code)
        history = self.client.get('/api/attempts').json()['attempts']
        self.assertEqual(1, len(history))
        self.assertIn('created_at', history[0])
        self.assertIsNone(history[0]['feedback_useful'])
        self.assertEqual(204, self.client.patch(f'/api/attempts/{self.attempt}/feedback', json={'useful':True}).status_code)
        self.assertTrue(self.client.get('/api/attempts').json()['attempts'][0]['feedback_useful'])
        self.assertEqual(404, self.client.patch(f'/api/attempts/{uuid.uuid4()}/feedback', json={'useful':False}).status_code)
        self.assertEqual({self.db, self.web}, set(Path(self.temp.name).iterdir()))
        self.assertEqual({self.db, self.web / 'index.html'}, {p for p in Path(self.temp.name).rglob('*') if p.is_file()})

    def test_valid_pass_retry_prepare_search_score_once(self):
        quality = scoring.QualityMeasurements(1, .1, .3, 1, 0, 0)
        for similarity, other, decision in [( .95, .8, 'pass'), (.7, .8, 'retry')]:
            self.attempt = str(uuid.uuid4())
            self.reference.search_target.reset_mock()
            self.reference.search_target.return_value.update(target_similarity=similarity, best_other_similarity=other, similarity_margin=similarity-other)
            with patch.object(api_server, 'prepare_sequence', wraps=prepare_sequence) as prepare, patch.object(scoring, 'measure_quality', return_value=quality), patch.object(scoring, 'manual_baseline_score', wraps=scoring.manual_baseline_score) as score, patch.object(api_server.PoseEmbeddingEncoder, 'encode_prepared_sequence', return_value=np.ones(4)) as encode:
                self.assertEqual(204, self.post().status_code)
                prepare.assert_not_called()
                self.reference.search_target.assert_not_called()
                result = self.post(True).json()
                self.assertEqual(decision, result['decision'])
                prepare.assert_called_once()
                encode.assert_called_once()
                score.assert_called_once()
                self.reference.search_target.assert_called_once()
                self.assertEqual('BLUE', result['nearest_confusion'])
                self.assertEqual([] if decision=='pass' else ['LOW_MATCH', 'NEAREST_CONFUSION'], [d['code'] for d in result['diagnostics']])
                self.assertNotIn('confidence', result)

    def test_concurrent_final_saves_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.post(True).json(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(1, self.detector.process.call_count)
        self.assertEqual(1, len(self.client.get('/api/attempts').json()['attempts']))

    def test_terminal_result_survives_new_api_instance(self):
        result = self.post(True).json()
        module = Mock()
        module.Holistic.return_value = Mock()
        with patch.object(api_server, 'get_holistic_module', return_value=module):
            with TestClient(api_server.build_app(self.reference, self.db, web_dir=self.web)) as client:
                wrong = client.post('/api/practice/frame', params=dict(attempt_id=self.attempt, target_word='BLUE', final=True), content=self.raw, headers={'Content-Type':'image/jpeg'})
                self.assertEqual(409, wrong.status_code)
                response = client.post('/api/practice/frame', params=dict(attempt_id=self.attempt, target_word='APPLE', final=True), content=self.raw, headers={'Content-Type':'image/jpeg'})
                self.assertEqual(result, response.json())
                module.Holistic.return_value.process.assert_not_called()

    def test_reference_filter_uses_original_indices(self):
        from asl_realtime.reference_index import ReferenceIndex
        root = Path(self.temp.name)
        np.savez(root / 'index.npz', embeddings=np.eye(3, dtype=np.float32))
        entries = [dict(word=w, slug=w, video_path='', embedding_index=i) for w, i in [('BLUE', 2), ('OUTSIDE', 0), ('APPLE', 1)]]
        (root / 'manifest.json').write_text(json.dumps({'entries': entries}))
        index = ReferenceIndex.load(root / 'index.npz', root / 'manifest.json', allowed_words=['APPLE', 'BLUE'])
        np.testing.assert_array_equal(index.embeddings, np.eye(3)[[2, 1]])
        result = index.search_target('APPLE', np.array([0, 1, 0]))
        self.assertEqual(1, result['target_similarity'])
        self.assertEqual('BLUE', result['best_other_word'])
        with self.assertRaisesRegex(ValueError, 'Missing reference words'):
            ReferenceIndex.load(root / 'index.npz', root / 'manifest.json', allowed_words=['MISSING'])

    def test_storage_failure_is_not_success(self):
        with patch.object(AttemptStore, 'save', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.post(True)
        self.assertEqual([], self.client.get('/api/attempts').json()['attempts'])

    def test_diagnostics_do_not_claim_incomplete_motion_or_position(self):
        m = scoring.QualityMeasurements(0, 0, 0, 0, 900, 900)
        result = diagnostics(m, scoring.quality_gate(m))
        self.assertEqual(['HANDS_NOT_VISIBLE', 'TOO_FEW_FRAMES'], [d['code'] for d in result])
        self.assertTrue(all(0 <= d['severity'] <= 1 for d in result))


if __name__ == '__main__':
    unittest.main()
