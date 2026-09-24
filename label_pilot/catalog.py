"""Lossless CSV import and local FTS search. Labels are hypotheses, not validation."""
import argparse
import collections
import csv
import json
import re
import sqlite3
from pathlib import Path

from .common import file_hash, write

QUERIES = {
    'risk': 'risk taking risks sacrifice uncertainty',
    'altruism': 'altruism altruistic selfless prosocial generosity generous charity charitable helping',
    'fairness': 'fairness equality equal distribution division',
    'creativity': 'creativity creative innovation originality unconventional',
}


def import_catalog(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    with source.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or []) != {'id', 'label', 'index_in_sae'}:
            raise ValueError('Expected id, label, index_in_sae columns')
        rows = list(reader)
    indices, uuids = set(), set()
    for row in rows:
        index = int(row['index_in_sae'])
        if index < 0 or index >= 65536 or index in indices or row['id'] in uuids:
            raise ValueError('Duplicate or invalid identifier')
        if not row['id'].strip() or not row['label'].strip():
            raise ValueError('Empty identifier or label')
        indices.add(index)
        uuids.add(row['id'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(destination) as db:
        db.execute('CREATE TABLE features (feature_id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, label TEXT NOT NULL)')
        db.execute('CREATE VIRTUAL TABLE labels_fts USING fts5(label, content=features, content_rowid=feature_id)')
        db.executemany('INSERT INTO features VALUES (?, ?, ?)',
                       [(int(r['index_in_sae']), r['id'], r['label']) for r in rows])
        db.execute("INSERT INTO labels_fts(labels_fts) VALUES ('rebuild')")
        db.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)')
        metadata = {'csv_sha256': file_hash(source), 'source_name': source.name,
                    'model_family_provenance': 'User identifies Goodfire Llama 3 70B SAE',
                    'filter_provenance': 'User reports omitted entries were withheld by Goodfire as harmful',
                    'identity_status': 'Check exact checkpoint against experiment pins; ten historical steering IDs/labels matched',
                    'interpretation_status': 'Supplied descriptions; not independently validated'}
        db.executemany('INSERT INTO metadata VALUES (?, ?)', metadata.items())
    counts = collections.Counter(r['label'] for r in rows)
    audit = dict(metadata, rows=len(rows), unique_labels=len(counts),
                 repeated_label_strings=sum(n > 1 for n in counts.values()),
                 missing_indices=sorted(set(range(65536)) - indices))
    write(destination.with_suffix('.audit.json'), audit)
    return {k: v for k, v in audit.items() if k != 'missing_indices'} | {'missing_count': len(audit['missing_indices'])}


def search(database, query, limit=10):
    terms = re.findall(r'[\w]+', query, flags=re.UNICODE)
    if not terms:
        return []
    # Quote tokens, never interpolate SQL or accept FTS syntax from the user.
    expression = ' OR '.join('"' + t.replace('"', '""') + '"' for t in terms)
    with sqlite3.connect(f'file:{Path(database).resolve()}?mode=ro', uri=True) as db:
        records = db.execute('SELECT f.feature_id,f.uuid,f.label,bm25(labels_fts) '
                             'FROM labels_fts JOIN features f ON f.feature_id=labels_fts.rowid '
                             'WHERE labels_fts MATCH ? ORDER BY bm25(labels_fts),f.feature_id LIMIT ?',
                             (expression, max(1, min(int(limit), 100)))).fetchall()
    return [dict(feature_id=r[0], uuid=r[1], label=r[2], retrieval_score=r[3],
                 selection_method='keyword_bm25', independently_validated=False) for r in records]


def feature(database, feature_id):
    with sqlite3.connect(f'file:{Path(database).resolve()}?mode=ro', uri=True) as db:
        row = db.execute('SELECT feature_id,uuid,label FROM features WHERE feature_id=?', (feature_id,)).fetchone()
    if row is None:
        raise ValueError(f'Feature {feature_id} absent from supplied catalog')
    return dict(feature_id=row[0], uuid=row[1], label=row[2])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    imp = sub.add_parser('import'); imp.add_argument('--csv', required=True); imp.add_argument('--db', required=True)
    find = sub.add_parser('search'); find.add_argument('--db', required=True); find.add_argument('query'); find.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(import_catalog(args.csv, args.db) if args.command == 'import'
                     else search(args.db, args.query, args.limit), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
