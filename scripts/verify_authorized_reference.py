"""Explicit private-asset check, separate from synthetic unit tests. Missing assets fail."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from asl_realtime.reference_index import ReferenceIndex, normalize_key
from signcoach_benchmark.config import load_config


def verify(root, expected_index_sha256, expected_manifest_sha256):
    for name, expected in [('index.npz', expected_index_sha256), ('manifest.json', expected_manifest_sha256)]:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f'Authorized asset required: {path}; no check was skipped.')
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected.lower():
            raise ValueError(f'{name}: SHA256 differs from the separately supplied trusted value')
    with np.load(root / 'index.npz', allow_pickle=False) as archive:
        vectors = archive['embeddings']
    if vectors.shape != (187, 22080) or not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) <= 1e-8):
        raise ValueError('Expected 187 finite, nonzero vectors of dimension 22080')
    index = ReferenceIndex.load(root / 'index.npz', root / 'manifest.json')
    counts = Counter(normalize_key(e.word) for e in index.entries)
    words = load_config().words
    if set(counts) != {normalize_key(w.asl_citizen_word) for w in words}:
        raise ValueError('Reference must cover exactly the configured 30 words')
    if any(':' in e.video_path or '\\' in e.video_path or e.video_path.startswith('/') for e in index.entries):
        raise ValueError('Manifest source identifiers must be portable, not absolute file paths')
    return {'verified': True, 'shape': list(vectors.shape),
            'counts': {w.target_word: counts[normalize_key(w.asl_citizen_word)] for w in words}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dir', type=Path, required=True)
    parser.add_argument('--expected-index-sha256', required=True)
    parser.add_argument('--expected-manifest-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.reference_dir, args.expected_index_sha256, args.expected_manifest_sha256), indent=2))
