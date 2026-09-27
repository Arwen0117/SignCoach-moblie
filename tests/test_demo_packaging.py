import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
from fastapi.testclient import TestClient
from asl_realtime import api_server
from asl_realtime.reference_index import ReferenceIndex, normalize_key
from asl_realtime.scoring import manual_baseline_score
from signcoach_benchmark.config import load_config


class PackagingTests(unittest.TestCase):
    def test_synthetic_reference_packaging_contract(self):
        # Artificial one-hot vectors, not ASL observations or a runtime fallback.
        words = load_config().words
        vectors = np.eye(len(words), dtype=np.float32)
        entries = [{'word': w.asl_citizen_word, 'slug': w.popsign_slug,
                    'video_path': f'synthetic/{i}', 'embedding_index': i}
                   for i, w in reversed(list(enumerate(words))) ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            np.savez(root / 'index.npz', embeddings=vectors)
            (root / 'manifest.json').write_text(json.dumps({'entries': entries}))
            index = ReferenceIndex.load(root / 'index.npz', root / 'manifest.json',
                                        allowed_words=[w.asl_citizen_word for w in words])
            np.testing.assert_array_equal(index.embeddings, vectors[::-1])
            self.assertEqual({normalize_key(w.asl_citizen_word) for w in words},
                             {normalize_key(e.word) for e in index.entries})
            for i, word in enumerate(words):
                result = index.search_target(word.asl_citizen_word, vectors[i])
                self.assertEqual(1.0, result['target_similarity'])
                self.assertEqual(0.0, result['best_other_similarity'])
                self.assertEqual('pass', manual_baseline_score(1.0, 1.0).decision)

    def test_missing_authorized_reference_fails_startup(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('sys.argv', ['server', '--reference-index', str(Path(temp) / 'missing.npz')]):
                with self.assertRaisesRegex(FileNotFoundError, 'separately authorized'):
                    api_server.main()

    def test_static_isolation_and_missing_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(FileNotFoundError, 'Frontend build missing'):
                api_server.build_app(Mock(), root / 'db', web_dir=root / 'web')
            web = root / 'web'
            (web / 'assets').mkdir(parents=True)
            (web / 'index.html').write_text('<html>Demo</html>')
            (web / 'assets/app.js').write_text('console.log("demo")')
            (web / 'assets/app.css').write_text('body{}')
            (root / 'secret.txt').write_text('private')
            # Even an accidental build file named api/unknown must not shadow API 404.
            (web / 'api').mkdir()
            (web / 'api/unknown').write_text('not an API')
            with patch.object(api_server, 'get_holistic_module', return_value=Mock()):
                with TestClient(api_server.build_app(Mock(), root / 'db', web_dir=web)) as client:
                    for path in ['/', '/assets/app.js', '/assets/app.css', '/api/health']:
                        self.assertEqual(200, client.get(path).status_code, path)
                    for path in ['/api/unknown', '/assets/missing.js', '/route', '/secret.txt', '/%2e%2e/secret.txt', '/deploy/reference/index.npz', '/data/signcoach-demo.sqlite3']:
                        self.assertEqual(404, client.get(path).status_code, path)
                    self.assertEqual('application/json', client.get('/api/unknown').headers['content-type'])

    def test_port_environment(self):
        with patch.dict(os.environ, {'PORT': '8123'}), patch('sys.argv', ['server']):
            self.assertEqual(8123, api_server.parse_args().port)
