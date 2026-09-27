"""Export the fixed Demo reference subset without changing source assets."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PureWindowsPath

import numpy as np

from asl_realtime.reference_index import ReferenceIndex, normalize_key
from asl_realtime.scoring import manual_baseline_score
from signcoach_benchmark.config import load_config


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def export_reference(index_path, manifest_path, output):
    words = load_config().words
    allowed = {normalize_key(w.asl_citizen_word) for w in words}
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    with np.load(index_path, allow_pickle=False) as archive:
        original = archive['embeddings']
    if original.ndim != 2 or original.shape[1] != 22080 or not np.isfinite(original).all():
        raise ValueError('Expected finite source vectors with dimension 22080')
    selected = [e for e in manifest['entries'] if normalize_key(e['word']) in allowed]
    indices = [e['embedding_index'] for e in selected]
    if len(set(indices)) != len(indices) or any(i < 0 or i >= len(original) for i in indices):
        raise ValueError('Invalid original embedding_index')
    counts = Counter(normalize_key(e['word']) for e in selected)
    if set(counts) != allowed or len(selected) != 187:
        raise ValueError('Expected the complete 187-entry, 30-word Demo reference')
    vectors = original[indices]
    if np.any(np.linalg.norm(vectors, axis=1) <= 1e-8):
        raise ValueError('Zero reference vector')
    entries = []
    for i, entry in enumerate(selected):
        entries.append({**entry, 'embedding_index': i,
                        'video_path': f"asl-citizen/{entry['word']}/{PureWindowsPath(entry['video_path']).name}"})
    output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output / 'index.npz', embeddings=vectors)
    (output / 'manifest.json').write_text(json.dumps({
        'encoder': manifest['encoder'], 'target_frames': manifest['target_frames'],
        'version': 'aslcitizen-demo30-v1', 'entries': entries,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    source = ReferenceIndex.load(index_path, manifest_path, allowed_words=tuple(w.asl_citizen_word for w in words))
    exported = ReferenceIndex.load(output / 'index.npz', output / 'manifest.json')
    np.testing.assert_array_equal(source.embeddings, exported.embeddings)
    # Every retained vector as query against every target: 5,610 equivalent searches/scores.
    for query in source.embeddings:
        for word in words:
            before = source.search_target(word.asl_citizen_word, query)
            after = exported.search_target(word.asl_citizen_word, query)
            if before != after:
                raise AssertionError('Search changed during export')
            if manual_baseline_score(before['target_similarity'], before['similarity_margin']) != manual_baseline_score(after['target_similarity'], after['similarity_margin']):
                raise AssertionError('Score changed during export')
    metadata = {
        'version': 'aslcitizen-demo30-v1', 'source': 'ASL Citizen local pose reference index',
        'source_index_sha256': sha256(index_path), 'source_manifest_sha256': sha256(manifest_path),
        'source_shape': list(original.shape), 'shape': list(vectors.shape), 'dtype': str(vectors.dtype),
        'index_sha256': sha256(output / 'index.npz'), 'manifest_sha256': sha256(output / 'manifest.json'),
        'index_bytes': (output / 'index.npz').stat().st_size,
        'manifest_bytes': (output / 'manifest.json').stat().st_size,
        'words': [{'target_word': w.target_word, 'reference_word': w.asl_citizen_word,
                   'entries': counts[normalize_key(w.asl_citizen_word)]} for w in words],
        'equivalence_checks': len(vectors) * len(words),
        'distribution': 'Local packaging only; public redistribution and commercial permissions require confirmation.',
    }
    (output / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8', newline='\n')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('deploy/reference'))
    args = parser.parse_args()
    print(json.dumps(export_reference(args.index, args.manifest, args.output), indent=2))
