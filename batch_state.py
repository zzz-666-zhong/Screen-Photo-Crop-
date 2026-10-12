"""Local batch checkpoints and reviewed labels; no automatic model fitting."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import tempfile

OPTION_NAMES = ('manual', 'review', 'retry_failed', 'recursive', 'square',
                'no_trim_black', 'black_threshold', 'max_trim', 'inset', 'overwrite', 'debug')


def atomic_json(path, data):
    path = Path(path)
    payload=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                         prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return None


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class BatchSession:
    def __init__(self, destination, source, files, args, version):
        self.destination, self.source = Path(destination), Path(source)
        self.files = list(files)
        self.names = [p.relative_to(source).as_posix() for p in self.files]
        self.path = self.destination/('manual_crop_session.json' if args.retry_failed else 'crop_session.json')
        self.options = {key: getattr(args, key) for key in OPTION_NAMES}
        old = read_json(self.path) if getattr(args, 'resume', False) else None
        if getattr(args, 'resume', False):
            if (not isinstance(old, dict) or old.get('schema') != 1
                    or not isinstance(old.get('source'),str) or not isinstance(old.get('options'),dict)
                    or not isinstance(old.get('records'),dict) or not isinstance(old.get('drafts'),dict)):
                raise ValueError('No readable batch checkpoint. Start a new batch first.')
            if Path(old['source']).resolve() != self.source.resolve() or old['options'] != self.options:
                raise ValueError('Resume must use the saved source and crop options. Use Resume in the workspace.')
        self.data = old or dict(schema=1, source=str(self.source), destination=str(self.destination),
            options=self.options, records={}, drafts={}, cursor=0, status='running', created_at=timestamp())
        self.data['files'] = self.names
        self.data['application_version'] = version
        self.data['records'] = {k:v for k,v in self.data['records'].items() if k in self.names}
        self.data['drafts'] = {k:v for k,v in self.data['drafts'].items() if k in self.names}
        self.index = min(max(0, int(self.data.get('cursor', 0))), len(self.files)) if old else 0
        if old and old.get('cursor_file') in self.names:self.index=self.names.index(old['cursor_file'])
        self.records, self.drafts = self.data['records'], self.data['drafts']
        self.persist()

    def persist(self, status=None):
        if status is not None: self.data['status'] = status
        self.data.update(cursor=self.index,cursor_file=self.names[self.index] if self.index<len(self.names) else None,
                         updated_at=timestamp())
        atomic_json(self.path, self.data)

    def draft(self, points, *, modified=False, automatic=None, source_sha256=''):
        if self.index >= len(self.names): return
        self.drafts[self.names[self.index]] = dict(points=[list(map(float,p)) for p in points],
            manual_modified=bool(modified), automatic_quad=automatic, source_sha256=source_sha256)
        self.persist()

    def pending(self, index):
        name = self.names[index]
        return name in self.drafts or self.records.get(name, {}).get('status') not in ('ok','existing','skipped','error')

    def first_pending(self):
        return next((i for i in range(len(self.names)) if self.pending(i)), len(self.names))

    def record(self, index, status, output, detail, **extra):
        name = self.names[index]
        previous = self.records.get(name, {})
        self.records[name] = dict(previous, input=name, output=output, status=status,
                                  detail=detail, updated_at=timestamp(), **extra)
        if status not in ('cancelled','paused'): self.drafts.pop(name, None)
        self.persist()
        self.write_report()

    def write_report(self):
        path = self.destination/('manual_crop_report.csv' if self.options['retry_failed'] else 'crop_report.csv')
        temporary = path.with_name(path.name+'.tmp')
        try:
            with temporary.open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.writer(stream); writer.writerow(['input','output','status','detail'])
                for name in self.names:
                    if name in self.records:
                        row = self.records[name]
                        writer.writerow([row.get(key,'') for key in ('input','output','status','detail')])
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


class LabelStore:
    def __init__(self, destination):
        self.destination = Path(destination)
        self.path = self.destination/'crop_labels.json'
        data = read_json(self.path)
        if self.path.exists() and (not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('items'),dict)):
            raise ValueError('crop_labels.json is unreadable; preserve it and choose another result directory.')
        self.data = data or dict(schema=1, coordinate_system='original pixels after EXIF orientation', items={})

    def save(self, source, quad, *, source_sha256, image_size, output, confirmed,
             modified, version, model_version, square, options):
        key = source_sha256
        previous = self.data['items'].get(key)
        # An unattended run must not replace a previously reviewed training label.
        if previous and previous['confirmed'] and not confirmed: return
        self.data['items'][key] = dict(id='capture_'+key[:20], group='capture_'+key,
            image=str(Path(source).resolve()), source_sha256=key, quad=quad,
            image_size=list(image_size), output=output, confirmed=bool(confirmed),
            manual_modified=bool(modified), application_version=version,
            model_version=model_version, square=bool(square), crop_options=options,
            updated_at=timestamp())
        atomic_json(self.path, self.data)

    def export(self, path):
        path = Path(path).resolve()
        if path.suffix.lower() != '.json':
            raise ValueError('Training labels must be exported to a .json file.')
        if path.name.lower() in ('crop_session.json','manual_crop_session.json','.crop-settings.json','screen_crop_model.json') or path == self.path.resolve():
            raise ValueError('Choose a separate export file, not crop_labels.json.')
        rows = []
        for row in self.data['items'].values():
            if not row['confirmed']: continue
            source = Path(row['image'])
            if not source.is_file() or fingerprint(source) != row['source_sha256']:
                raise ValueError('A labeled original is missing or changed: '+str(source))
            rows.append({key:row[key] for key in ('id','group','image','source_sha256','quad','square',
                                                'manual_modified','application_version','model_version')})
            rows[-1]['split'] = 'train'
        if not rows: raise ValueError('No human-confirmed crops to export yet.')
        atomic_json(path, rows)
        return len(rows)


def label_source(path, destination, relative, retry, digest):
    if not retry: return path
    # Resolve failure copies back to the retained originals when possible.
    previous = read_json(Path(destination)/'crop_session.json')
    if isinstance(previous, dict):
        candidate = (Path(previous['source'])/relative).resolve()
        if candidate.is_relative_to(Path(previous['source']).resolve()) and candidate.is_file():
            if fingerprint(candidate) == digest: return candidate
    # A retry copy may be the only original available. Retain a local label source
    # before the successful retry removes the failure copy.
    retained = Path(destination)/'label_sources'/(digest+path.suffix.lower())
    if not retained.exists():
        retained.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(path, retained)
    return retained


def load_preferences(path):
    data = read_json(path)
    return data if isinstance(data, dict) else {}
