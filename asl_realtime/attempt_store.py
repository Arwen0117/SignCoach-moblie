"""Local terminal-attempt storage; never stores camera media."""
from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class AttemptStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS attempts (attempt_id TEXT PRIMARY KEY, result TEXT NOT NULL, features TEXT NOT NULL, created_at TEXT NOT NULL, feedback_useful INTEGER)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, attempt_id):
        with self.connect() as db:
            row = db.execute('SELECT result FROM attempts WHERE attempt_id=?', (attempt_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, result, features):
        with self.connect() as db:
            db.execute('INSERT INTO attempts VALUES (?, ?, ?, ?, NULL)', (
                result['attempt_id'], json.dumps(result, allow_nan=False),
                json.dumps(features, allow_nan=False), datetime.now(timezone.utc).isoformat()))

    def recent(self, limit):
        with self.connect() as db:
            rows = db.execute('SELECT result, created_at, feedback_useful FROM attempts ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        return [{**json.loads(result), 'created_at': created, 'feedback_useful': None if useful is None else bool(useful)} for result, created, useful in rows]

    def feedback(self, attempt_id, useful):
        with self.connect() as db:
            return db.execute('UPDATE attempts SET feedback_useful=? WHERE attempt_id=?', (int(useful), attempt_id)).rowcount != 0
