"""Checkout-local history stored outside the business repository."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import quote

from _contracts import Invalid, problem, text


def state_invalid(path, reason):
    raise Invalid('state-invalid', [problem(f'{path}：{reason}')])


def check_access(path, info=None):
    try:
        info = path.lstat() if info is None else info
        if stat.S_ISLNK(info.st_mode):
            state_invalid(path, '状态路径含符号链接')
        directory = stat.S_ISDIR(info.st_mode)
        if not directory and not stat.S_ISREG(info.st_mode):
            state_invalid(path, '状态路径必须是目录或普通文件')
        checks = [(0o444, os.R_OK, '不可读取'), (0o222, os.W_OK, '不可写入')]
        if directory:
            checks.append((0o111, os.X_OK, '目录不可访问'))
        for bits, access, reason in checks:
            if not info.st_mode & bits or not os.access(path, access):
                state_invalid(path, reason)
    except OSError as error:
        state_invalid(path, error)


def read_record(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        state_invalid(path, f'无法读取或解析记录：{error}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def now():
    return datetime.now(timezone.utc).isoformat()


def run_git(root, *args):
    try:
        return subprocess.run(['git', '--no-optional-locks', '-C', str(root), *args], capture_output=True)
    except OSError as error:
        state_invalid(root, f'无法运行 git：{error}')


def git_failure(root, args, process):
    reason = process.stderr.decode('utf-8', errors='replace').strip() or f'退出码 {process.returncode}'
    state_invalid(root, f'git {" ".join(args)} 无法读取仓库状态：{reason}')


def git(root, *args):
    process = run_git(root, *args)
    if process.returncode:
        git_failure(root, args, process)
    return process.stdout


def repository_root(location):
    location = Path(location).absolute()
    args = ('rev-parse', '--show-toplevel')
    process = run_git(location, *args)
    if process.returncode:
        markers = [parent / '.git' for parent in (location, *location.parents)]
        if process.returncode == 128 and not any(p.exists() or p.is_symlink() for p in markers):
            raise Invalid('not-a-git-repository', [problem('不在 Git 仓库中')])
        git_failure(location, args, process)
    return Path(os.fsdecode(process.stdout).strip()).resolve()


def head_commit(root):
    args = ('rev-parse', '--verify', '--quiet', 'HEAD')
    process = run_git(root, *args)
    if process.returncode == 0:
        return process.stdout.decode('ascii').strip()
    if process.returncode != 1:
        git_failure(root, args, process)
    # A symbolic HEAD whose branch has no ref is a valid repository without a commit.
    args = ('symbolic-ref', '--quiet', 'HEAD')
    symbolic = run_git(root, *args)
    if symbolic.returncode:
        git_failure(root, args, symbolic)
    args = ('show-ref', '--verify', '--quiet', os.fsdecode(symbolic.stdout).strip())
    reference = run_git(root, *args)
    if reference.returncode == 1:
        return None
    if reference.returncode:
        git_failure(root, args, reference)
    state_invalid(root, 'HEAD 引用存在但无法解析提交号')


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
        try:
            if path.is_symlink():
                value = digest(os.fsencode(os.readlink(path)))
                files.append(dict(path=name, sha256=value))
            elif not path.exists():
                files.append(dict(path=name, deleted=True))
            else:
                files.append(dict(path=name, sha256=digest(path.read_bytes())))
        except FileNotFoundError:
            files.append(dict(path=name, deleted=True))
        except OSError as error:
            state_invalid(path, f'无法读取产品文件：{error}')
    return dict(product_fingerprint=digest(canonical(files)),
                commit=head_commit(root),
                dirty=bool(git(root, 'status', '--porcelain', '--untracked-files=all')))


def ratio(numerator, denominator):
    return dict(numerator=numerator, denominator=denominator,
                rate=numerator / denominator if denominator else None)


def statistics(rows):
    counts = {status: sum(row['status'] == status for row in rows)
              for status in ('pass', 'fail', 'blocked', 'skip')}
    return dict(executed=len(rows), **counts, pass_rate=ratio(counts['pass'], len(rows)))


def write_json(path, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding='utf-8')
    except OSError as error:
        state_invalid(path, error)


class State:
    def __init__(self, root, scenario, batch):
        base = Path(os.environ.get('SOP_VERIFY_STATE') or
                    str(Path(os.environ.get('XDG_STATE_HOME') or '~/.local/state').expanduser() / 'sop-verify'))
        self.root = root
        self.base = base.expanduser().absolute()
        name = root.name + '-' + digest(str(root).encode('utf-8'))[:12]
        batch_name = quote(batch, safe='')
        if batch_name in ('.', '..'):
            batch_name = batch_name.replace('.', '%2E')
        self.directory = self.base / name / batch_name
        self.scenario_file = scenario.relative_to(root).as_posix()
        self.batch = batch
        self.writable()
        self.binding()

    def binding(self):
        marker = self.directory / 'batch.json'
        if marker.exists():
            record = read_record(marker)
            if not isinstance(record, dict) or not text(record.get('scenario_file')):
                state_invalid(marker, '批次记录缺少有效的 scenario_file')
            if record.get('scenario_file') != self.scenario_file:
                raise Invalid('batch-conflict', [problem(
                    f'批次 {self.batch} 已属于 {record.get("scenario_file")}，不能用于 {self.scenario_file}')])

    def bind(self):
        """Board mode retains only the local batch-to-path binding."""
        if not (self.directory / 'batch.json').exists():
            with self.staging() as staged:
                self.publish(staged, [])

    def writable(self):
        try:
            resolved = self.base.resolve()
        except (OSError, RuntimeError) as error:
            state_invalid(self.base, error)
        if resolved.is_relative_to(self.root):
            state_invalid(self.base, '状态目录必须位于业务仓库外')
        ancestor = self.base
        while True:
            try:
                info = ancestor.lstat() if ancestor == self.base else ancestor.stat()
                break
            except FileNotFoundError:
                ancestor = ancestor.parent
            except OSError as error:
                state_invalid(ancestor, error)
        check_access(ancestor, info)
        if not stat.S_ISDIR(info.st_mode):
            state_invalid(ancestor, '状态路径必须是目录')
        if ancestor != self.base:
            return

        def walk_error(error):
            state_invalid(error.filename, error)

        for parent, directories, files in os.walk(self.base, onerror=walk_error, followlinks=False):
            for name in directories + files:
                path = Path(parent) / name
                check_access(path)
                tail = path.relative_to(self.base).parts[2:]
                record = (tail == ('batch.json',) or tail == ('cases', 'union.json')
                          or (len(tail) == 3 and tail[0] == 'rounds' and tail[2] == 'round.json')
                          or (len(tail) == 3 and tail[:2] == ('cases', 'imports') and path.suffix == '.json')
                          or (len(tail) == 2 and tail[0] == 'coverage' and path.suffix == '.json'))
                if name in files and record:
                    read_record(path)

    def rounds(self):
        folder = self.directory / 'rounds'
        if not folder.exists():
            return []
        try:
            paths = list(folder.iterdir())
        except OSError as error:
            state_invalid(folder, error)
        for path in paths:
            if not path.is_dir() or not path.name.isdecimal() or int(path.name) < 1:
                state_invalid(path, '轮次目录必须使用正整数编号')
        records = []
        for path in sorted(paths, key=lambda p: int(p.name)):
            record_path = path / 'round.json'
            record = read_record(record_path)
            if (not isinstance(record, dict) or record.get('data_version') != 1
                    or record.get('kind') != 'sop-round'
                    or record.get('round') != int(path.name)
                    or not text(record.get('product_fingerprint'))
                    or not isinstance(record.get('results'), list)):
                state_invalid(record_path, '轮次记录结构不完整或版本无效')
            for row in record['results']:
                if (not isinstance(row, dict)
                        or not all(text(row.get(key)) for key in
                                   ('scenario', 'actual', 'executor', 'executed_at', 'content_fingerprint'))
                        or row.get('status') not in ('pass', 'fail', 'blocked', 'skip')
                        or row.get('independence') not in ('self-check', 'independent', 'undeclared')
                        or not isinstance(row.get('evidence'), list)
                        or any(not isinstance(e, dict) or not text(e.get('path')) or not text(e.get('sha256'))
                               for e in row['evidence'])
                        or (row['status'] in ('blocked', 'skip') and not text(row.get('finding')))):
                    state_invalid(record_path, '轮次结果结构不完整')
            if record.get('statistics') != statistics(record['results']):
                state_invalid(record_path, '轮次统计与结果不一致')
            records.append(record)
        return records

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

    @contextmanager
    def staging(self):
        self.writable()
        try:
            self.directory.parent.mkdir(parents=True, exist_ok=True)
            temporary = tempfile.TemporaryDirectory(prefix='.sop-', dir=self.directory.parent)
        except OSError as error:
            state_invalid(self.directory.parent, error)
        with temporary:
            yield Path(temporary.name) / 'batch'

    def publish(self, staged, selections, replace=()):
        self.writable()
        self.binding()
        for name in selections:
            target = self.directory / name
            if target.exists() and name not in replace:
                state_invalid(target, '目标记录已存在，请重新读取状态后登记')
        marker = self.directory / 'batch.json'
        if not marker.exists():
            if self.directory.exists():
                state_invalid(marker, '已有批次目录缺少绑定记录')
            write_json(staged / 'batch.json', dict(scenario_file=self.scenario_file))
            try:
                os.rename(staged, self.directory)
            except OSError as error:
                state_invalid(self.directory, error)
            return

        # Payloads are complete before any live record is replaced; retain originals for rollback.
        installed, backups, created = [], {}, []
        target = self.directory
        try:
            for index, name in enumerate(selections):
                target = self.directory / name
                missing = []
                parent = target.parent
                while not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for parent in reversed(missing):
                    parent.mkdir()
                    created.append(parent)
                if target.exists():
                    backup = staged.parent / f'backup-{index}'
                    os.replace(target, backup)
                    backups[target] = backup
                os.replace(staged / name, target)
                installed.append(target)
        except OSError as error:
            try:
                for path in reversed(installed):
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                for path, backup in backups.items():
                    os.replace(backup, path)
                for path in reversed(created):
                    path.rmdir()
            except OSError as rollback_error:
                state_invalid(target, f'{error}；恢复原记录失败：{rollback_error}')
            state_invalid(target, error)

    def submit(self, scenario, rows, fingerprints, source, implementer, scenario_sha, entry):
        rounds = self.rounds()
        number = len(rounds) + 1
        with self.staging() as staged:
            selection = f'rounds/{number}'
            folder = staged / selection
            record = self.stage_round(folder, scenario, rows, fingerprints, source, implementer,
                                      scenario_sha, number)
            if (digest(scenario.read_bytes()) != scenario_sha or
                    product(self.root, scenario, entry)['product_fingerprint'] != source['product_fingerprint']):
                raise Invalid('source-stale', [problem('登记期间场景文件或产品发生变化')])
            self.publish(staged, [selection])
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
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                except OSError as error:
                    state_invalid(target, error)
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
        if not path.exists():
            return []
        record = read_record(path)
        if (not isinstance(record, dict) or not isinstance(record.get('test_cases'), list)
                or any(not isinstance(item, dict) or not text(item.get('id')) or not text(item.get('title'))
                       for item in record['test_cases'])):
            state_invalid(path, '用例并集必须包含有效的 test_cases 数组')
        return record['test_cases']

    def save_snapshot(self, area, value, additional=None):
        self.writable()
        self.binding()
        folder = self.directory / area
        try:
            snapshots = list(folder.glob('*.json'))
        except OSError as error:
            state_invalid(folder, error)
        for path in snapshots:
            if not path.stem.isdecimal():
                state_invalid(path, '快照文件必须使用整数编号')
        number = max((int(p.stem) for p in snapshots), default=0) + 1
        selection = f'{area}/{number:06}.json'
        with self.staging() as staged:
            write_json(staged / selection, value)
            for name, content in (additional or {}).items():
                write_json(staged / name, content)
            self.publish(staged, [selection, *(additional or {})], replace=tuple(additional or {}))
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
                                                source_sha256=digest(path.read_bytes()), document=document),
                           {'cases/union.json': dict(test_cases=list(union.values()))})
        return dict(**counts, total=len(union))
