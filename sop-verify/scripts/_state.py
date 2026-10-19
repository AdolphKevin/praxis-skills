"""Checkout-local history stored outside the business repository."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote

from _contracts import Invalid, problem


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def now():
    return datetime.now(timezone.utc).isoformat()


def git(root, *args):
    process = subprocess.run(['git', '--no-optional-locks', '-C', str(root), *args], capture_output=True)
    if process.returncode:
        raise Invalid('source-stale', [problem('git 无法读取产品状态')])
    return process.stdout


def product(root, scenario, entry):
    names = set(git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0'))
    files = []
    excluded = {scenario, entry}
    for raw in sorted(names):
        if not raw:
            continue
        name = os.fsdecode(raw)
        path = root / name
        if name.startswith('docs/sop/') or path.resolve() in excluded:
            continue
        if path.is_symlink():
            value = digest(os.fsencode(os.readlink(path)))
            files.append(dict(path=name, sha256=value))
        elif not path.exists():
            files.append(dict(path=name, deleted=True))
        else:
            files.append(dict(path=name, sha256=digest(path.read_bytes())))
    head = subprocess.run(['git', '--no-optional-locks', '-C', str(root), 'rev-parse', '--verify', 'HEAD'], capture_output=True, text=True)
    return dict(product_fingerprint=digest(canonical(files)),
                commit=head.stdout.strip() if head.returncode == 0 else None,
                dirty=bool(git(root, 'status', '--porcelain', '--untracked-files=all')))


def ratio(numerator, denominator):
    return dict(numerator=numerator, denominator=denominator,
                rate=numerator / denominator if denominator else None)


def statistics(rows):
    counts = {status: sum(row['status'] == status for row in rows)
              for status in ('pass', 'fail', 'blocked', 'skip')}
    return dict(executed=len(rows), **counts, pass_rate=ratio(counts['pass'], len(rows)))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class State:
    def __init__(self, root, scenario, batch):
        base = Path(os.environ.get('SOP_VERIFY_STATE') or
                    str(Path(os.environ.get('XDG_STATE_HOME') or '~/.local/state').expanduser() / 'sop-verify'))
        self.root = root
        self.base = base.expanduser().resolve()
        name = root.name + '-' + digest(str(root).encode('utf-8'))[:12]
        batch_name = quote(batch, safe='')
        if batch_name in ('.', '..'):
            batch_name = batch_name.replace('.', '%2E')
        self.directory = self.base / name / batch_name
        self.scenario_file = scenario.relative_to(root).as_posix()
        self.batch = batch
        self.binding()

    def binding(self):
        marker = self.directory / 'batch.json'
        if marker.exists():
            record = json.loads(marker.read_text(encoding='utf-8'))
            if record.get('scenario_file') != self.scenario_file:
                raise Invalid('batch-conflict', [problem(
                    f'批次 {self.batch} 已属于 {record.get("scenario_file")}，不能用于 {self.scenario_file}')])

    def writable(self):
        if (self.directory.resolve().is_relative_to(self.root)
                or any(p.is_symlink() for p in self.directory.rglob('*'))):
            raise Invalid('source-stale', [problem('状态目录必须位于业务仓库外')])

    def rounds(self):
        folder = self.directory / 'rounds'
        if not folder.exists():
            return []
        return [json.loads(p.read_text(encoding='utf-8'))
                for p in sorted(folder.glob('*/round.json'), key=lambda p: int(p.parent.name))]

    def pending(self, scenarios, fingerprints, source):
        rounds = self.rounds()
        result = dict(pending=[], guarded=[], blocked=[])
        for s in scenarios:
            ident = s['id']
            history = [(r, row) for r in rounds for row in r['results'] if row['scenario'] == ident]
            current = [(r, row) for r, row in history
                       if row['content_fingerprint'] == fingerprints[ident]]
            reason = None
            if not history:
                reason = 'new'
            elif not current:
                reason = 'changed'
            else:
                round_, row = current[-1]
                if row['status'] in ('blocked', 'skip'):
                    result['blocked'].append(dict(scenario=ident, status=row['status'], finding=row['finding']))
                elif row['status'] == 'fail':
                    reason = 'failed'
                elif round_['product_fingerprint'] != source['product_fingerprint']:
                    if 'check' in s.get('regression', {}):
                        result['guarded'].append(dict(scenario=ident, check=s['regression']['check'],
                                                     message='需确认该检查在当前源码通过'))
                    else:
                        reason = 'source-changed'
            if reason:
                result['pending'].append(dict(scenario=ident, reason=reason))
        return result

    def submit(self, scenario, rows, fingerprints, source, implementer, scenario_sha, entry):
        rounds = self.rounds()
        number = len(rounds) + 1
        self.writable()
        self.directory.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.submit-', dir=self.directory.parent) as temporary:
            folder = Path(temporary) / 'round'
            record = self.stage_round(folder, scenario, rows, fingerprints, source, implementer,
                                      scenario_sha, number)
            if (digest(scenario.read_bytes()) != scenario_sha or
                    product(self.root, scenario, entry)['product_fingerprint'] != source['product_fingerprint']):
                raise Invalid('source-stale', [problem('登记期间场景文件或产品发生变化')])
            self.binding()
            self.writable()
            target = self.directory / 'rounds' / str(number)
            if target.exists():
                raise Invalid('source-stale', [problem('轮次已变化，请重新登记')])
            write_json(self.directory / 'batch.json', dict(scenario_file=self.scenario_file))
            target.parent.mkdir(parents=True, exist_ok=True)
            os.rename(folder, target)
            return record

    def stage_round(self, folder, scenario, rows, fingerprints, source, implementer, scenario_sha, number):
        results = []
        for row in rows:
            row = dict(row)
            executor = ' '.join(row['executor'].casefold().split())
            author = ' '.join(implementer.casefold().split()) if implementer is not None else None
            row['independence'] = ('undeclared' if author is None else
                                   'self-check' if executor == author else 'independent')
            row['content_fingerprint'] = fingerprints[row['scenario']]
            evidence = []
            for index, path in enumerate(row['evidence']):
                data = path.read_bytes()
                relative = f'evidence/{len(results) + 1}/{index + 1}-{path.name}'
                target = folder / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                evidence.append(dict(path=relative, sha256=digest(data)))
            row['evidence'] = evidence
            results.append(row)
        record = dict(data_version=1, kind='sop-round', batch=self.batch,
                      scenario_file=self.scenario_file, scenario_sha256=scenario_sha,
                      round=number, **source, implementer=implementer, submitted_at=now(),
                      results=results, statistics=statistics(results))
        write_json(folder / 'round.json', record)
        return record

    def cases(self):
        path = self.directory / 'cases/union.json'
        return json.loads(path.read_text(encoding='utf-8'))['test_cases'] if path.exists() else []

    def save_snapshot(self, area, value):
        self.writable()
        self.binding()
        folder = self.directory / area
        number = max((int(p.stem) for p in folder.glob('*.json')), default=0) + 1
        write_json(self.directory / 'batch.json', dict(scenario_file=self.scenario_file))
        write_json(folder / f'{number:06}.json', value)
        return number

    def import_cases(self, path, document, items):
        union = {item['id']: item for item in self.cases()}
        counts = dict(added=0, updated=0, unchanged=0)
        for item in items:
            ident = item['id']
            category = 'added' if ident not in union else 'unchanged' if item == union[ident] else 'updated'
            counts[category] += 1
            union[ident] = item
        self.save_snapshot('cases/imports', dict(imported_at=now(), source=path.read_text(encoding='utf-8'),
                                                source_sha256=digest(path.read_bytes()), document=document))
        write_json(self.directory / 'cases/union.json', dict(test_cases=list(union.values())))
        return dict(**counts, total=len(union))
