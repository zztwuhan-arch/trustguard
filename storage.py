"""Local single-user demo store. Transactions and revisions prevent stale overwrites."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv('TRUSTGUARD_DB') or Path(__file__).parent / 'data' / 'trustguard.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def all(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT body FROM cases ORDER BY rowid DESC')]

    def get(self, case_id):
        with self.connect() as db:
            row = db.execute('SELECT body FROM cases WHERE id=?', (case_id,)).fetchone()
        if not row:
            raise ValueError('Case not found')
        return json.loads(row[0])

    def create(self, content, market, review):
        case = {'id': str(uuid4()), 'revision': 0, 'created_at': now(), 'content': content,
                'market': market, 'review': review.model_dump(), 'final_action': None,
                'status': 'pending_human' if review.decision.human_required else 'reviewed',
                'appeals': [], 'events': [{'at': now(), 'type': 'analysis', 'mode': review.mode}]}
        with self.connect() as db:
            db.execute('INSERT INTO cases VALUES (?, ?, ?)', (case['id'], 0, json.dumps(case)))
        return case

    def _save(self, case, revision):
        case['revision'] = revision + 1
        with self.connect() as db:
            updated = db.execute('UPDATE cases SET revision=?, body=? WHERE id=? AND revision=?',
                                 (case['revision'], json.dumps(case), case['id'], revision))
            if updated.rowcount != 1:
                raise ValueError('Case changed in another session; reload before submitting')
        return case

    def appeal(self, case_id, appeal, expected_revision):
        case = self.get(case_id)
        if case['revision'] != expected_revision:
            raise ValueError('Case changed during appeal review; reload and try again')
        if any(a['status'] == 'pending' for a in case['appeals']):
            raise ValueError('This case already has an open appeal')
        case['appeals'].append(appeal.model_dump())
        case['status'] = 'appeal_pending'
        case['events'].append({'at': now(), 'type': 'appeal_submitted'})
        return self._save(case, expected_revision)

    def resolve(self, case_id, action, reviewer, rationale, expected_revision):
        if action not in ('allow', 'warn', 'remove') or not reviewer.strip() or not rationale.strip():
            raise ValueError('Action, reviewer name and rationale are required')
        case = self.get(case_id)
        if case['revision'] != expected_revision:
            raise ValueError('Case changed; reload before submitting')
        if case['status'] == 'resolved':
            raise ValueError('Already resolved; submit an appeal to reopen')
        pending = [a for a in case['appeals'] if a['status'] == 'pending']
        if pending:
            appeal = pending[-1]
            appeal.update(status='resolved', final_action=action,
                          overturned=(appeal['prior_action'] != action) if appeal['prior_action'] is not None else None)
        case['final_action'] = action
        case['status'] = 'resolved'
        case['events'].append({'at': now(), 'type': 'human_resolution', 'reviewer': reviewer.strip(),
                               'action': action, 'rationale': rationale.strip(), 'is_appeal': bool(pending)})
        return self._save(case, expected_revision)


def appeal_metrics(cases):
    appeals = [a for c in cases for a in c['appeals']]
    resolved = [a for a in appeals if a['status'] == 'resolved']
    eligible = [a for a in resolved if a['prior_action'] is not None]
    overturned = sum(a['overturned'] is True for a in eligible)
    return {'submitted': len(appeals), 'resolved': len(resolved), 'eligible_resolved': len(eligible),
            'overturned': overturned, 'overturn_rate': overturned / len(eligible) if eligible else None}
