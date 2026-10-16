"""Explicit operator decisions for isolated API fixtures, never real assets."""
from app import pet_quality
from app.db import get_db


def approve_quality(task, through='motion'):
    db = get_db()
    for stage in pet_quality.STAGES[:pet_quality.STAGES.index(through)+1]:
        pet_quality.record(db, task, stage, pet_quality.fingerprints(db, task)[stage], 'pass',
                           {'notes': 'Synthetic test fixture reviewed', 'files': [{'sha256': 'test-only'}]})
    db.commit()
