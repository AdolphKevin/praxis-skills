"""Standard-library client for the standalone SOP board."""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from pathlib import Path

from _contracts import Invalid, problem
from _state import run_git, git_failure, product, digest, state_invalid


def project_identity(root):
    override = os.environ.get('SOP_BOARD_PROJECT')
    value = override or ''
    if not value:
        remote = run_git(root, 'remote', 'get-url', 'origin')
        if remote.returncode not in (0, 2):
            git_failure(root, ('remote', 'get-url', 'origin'), remote)
        value = remote.stdout.decode('utf-8').strip() if remote.returncode == 0 else ''
    if not value:
        raise Invalid('project-identity-missing', [problem('未找到 origin，请设置 SOP_BOARD_PROJECT')])
    if '://' in value:
        url = urlsplit(value)
        value = (url.hostname or '') + '/' + url.path.lstrip('/')
    else:
        value = re.sub(r'^(?:[^/@]+@)?([^/:]+):', r'\1/', value)
    return re.sub(r'\.git$', '', value.lower())


def redact(value):
    token = os.environ.get('SOP_BOARD_TOKEN', '')
    if isinstance(value, str):
        return value.replace(token, '***') if token else value
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


class Board:
    def __init__(self, root, batch=''):
        self.root = root
        self.url = os.environ['SOP_BOARD_URL'].rstrip('/')
        self.identity = project_identity(root)
        self.key = re.sub('[^a-z0-9]+', '-', self.identity.lower()).strip('-')
        self.batch = batch
        self.api = '/api/v1/projects/' + quote(self.key, safe='') + '/batches/' + quote(batch, safe='')
        self.page = self.url + '/p/' + quote(self.key, safe='') + '/b/' + quote(batch, safe='')

    def request(self, path, *, method='GET', body=None, headers=None, missing=(), raw_response=False):
        address = self.url + path
        headers = dict(headers or {})
        if method != 'GET':
            token = os.environ.get('SOP_BOARD_TOKEN')
            if not token:
                raise Invalid('board-token-missing', [problem('写入看板需要 SOP_BOARD_TOKEN')])
            headers['Authorization'] = 'Bearer ' + token
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            headers['Content-Type'] = 'application/json; charset=utf-8'
        try:
            try:
                with urlopen(Request(address, data=body, headers=headers, method=method), timeout=30) as response:
                    status, raw = response.status, response.read()
            except HTTPError as error:
                status, raw = error.code, error.read()
            if raw_response and status < 400:
                return raw.decode('utf-8')
            value = json.loads(raw.decode('utf-8'))
            if not isinstance(value, dict):
                raise ValueError('JSON 响应必须是对象')
        except (json.JSONDecodeError, UnicodeError) as error:
            raise Invalid('board-unavailable', [problem(f'{address}：响应不是 JSON：{error}')]) from error
        except (URLError, OSError, ValueError) as error:
            raise Invalid('board-unavailable', [problem(f'{address}：{error}')]) from error
        if status >= 400 or value.get('ok') is False:
            code = value.get('error_code', f'HTTP {status}')
            if status == 404 and code in missing:
                return None
            problems = [problem('看板错误代码 ' + code)]
            problems.extend(problem(f"{item['field']}：{item['problem']}", item.get('line'))
                            for item in value.get('problems', []))
            raise Invalid('board-rejected', problems)
        return value

    def status(self):
        response = self.request('/api/v1/projects/' + quote(self.key, safe='') + '/attention',
                                missing=('project-not-found',))
        result = dict(ok=True, board=self.url, project=self.key, items=response['items'] if response else [])
        if response is None:
            result['warnings'] = ['看板上还没有项目 ' + self.key]
        return result

    def pending(self, scenarios, fingerprints, source=None):
        response = self.request(self.api + '/scenarios', missing=('batch-not-found', 'project-not-found'))
        remote = {item['scenario']: item for item in response['scenarios']} if response else {}
        result = dict(pending=[], guarded=[], blocked=[], board_url=self.page, warnings=[])
        for scenario in scenarios:
            ident = scenario['id']
            item = remote.get(ident)
            history = []
            if item:
                history = [(row, kind) for kind in ('agent', 'manual')
                           if (row := item.get('latest_' + kind))]
            latest, kind = max(history, key=lambda pair: pair[0].get('round', pair[0].get('number', 0))) if history else (None, None)
            reason = None
            if item is None:
                reason = 'new'
            elif item['fingerprint'] != fingerprints[ident]:
                reason = 'changed'
            elif 'check' in scenario.get('regression', {}) and item.get('regression_status') == 'failed':
                reason = 'failed'
            elif latest and (latest['status'] == 'fail' or (kind == 'manual' and latest['status'] == 'blocked')):
                reason = 'failed'
            elif latest and latest['status'] in ('blocked', 'skip'):
                result['blocked'].append(dict(scenario=ident, status=latest['status'], finding=latest.get('finding', '')))
            elif 'check' in scenario.get('regression', {}):
                result['guarded'].append(dict(scenario=ident, check=scenario['regression']['check'],
                                             message='检查通过' if item.get('regression_status') == 'passed' else '检查待运行'))
            elif latest is None:
                reason = 'new'
            elif item.get('queue') == 'pending' and (item.get('latest_agent') or {}).get('status') == 'pass':
                reason = 'source-changed'
            if reason:
                result['pending'].append(dict(scenario=ident, reason=reason))
        if source is not None:
            result['product_fingerprint'] = source['product_fingerprint']
            summary = self.request(self.api, missing=('batch-not-found', 'project-not-found')) if response else None
            if summary and summary.get('product_digest') and summary['product_digest'] != source['product_fingerprint']:
                result['warnings'].append('本机有未推送的产品改动，看板的待执行判断基于已推送的版本')
        return result

    def report(self, format):
        result = self.request(self.api if format == 'json' else self.api + '/report.md',
                              raw_response=format != 'json')
        return dict(ok=True, batch=result) if format == 'json' else result

    def assert_current(self, path, entry_path, scenario_sha, source):
        try:
            current = digest(path.read_bytes())
        except FileNotFoundError:
            current = None
        except OSError as error:
            state_invalid(path, error)
        if current != scenario_sha or product(self.root, path, entry_path)['product_fingerprint'] != source['product_fingerprint']:
            raise Invalid('source-stale', [problem('登记期间场景文件或产品发生变化')])

    def author(self):
        user = run_git(self.root, 'config', 'user.name')
        if user.returncode not in (0, 1):
            git_failure(self.root, ('config', 'user.name'), user)
        return user.stdout.decode('utf-8').strip() or 'sop-verify'

    def import_cases(self, path):
        return self.request(self.api + '/cases', method='POST', body=dict(
            filename=path.name, content=path.read_text(encoding='utf-8'), uploaded_by=self.author()))

    def submit(self, path, scenario_bytes, document, entries, entry_path, scenarios,
               fingerprints, source, rows, results_bytes, implementer):
        if not os.environ.get('SOP_BOARD_TOKEN'):
            raise Invalid('board-token-missing', [problem('写入看板需要 SOP_BOARD_TOKEN')])
        missing = {item['scenario'] for item in self.pending(scenarios, fingerprints)['pending']} - {
            row['scenario'] for row in rows}
        if missing:
            raise Invalid('scenario-results-incomplete', [problem('缺少场景 ' + ident) for ident in sorted(missing)])
        scenario_sha = digest(scenario_bytes)
        self.assert_current(path, entry_path, scenario_sha, source)
        pushed_by = self.author()
        push = dict(project=dict(id=self.identity, name=self.root.name),
                    path=path.relative_to(self.root).as_posix(), commit=source['commit'], dirty=source['dirty'],
                    product_digest=source['product_fingerprint'], content=scenario_bytes.decode('utf-8'),
                    fingerprints=fingerprints, pushed_by=pushed_by, entries=entries)
        sources = []
        for item in document['metadata']['sources']:
            for name in item['ref'].split():
                name = name.split('#', 1)[0]
                candidate = Path(name)
                target = (self.root / candidate).resolve()
                if candidate.is_absolute() or not target.is_relative_to(self.root) or not target.is_file():
                    continue
                try:
                    raw = target.read_bytes()
                    content = raw.decode('utf-8')
                except (OSError, UnicodeError) as error:
                    raise Invalid('scenario-file-invalid', [problem(f'SOP 原文 {name} 无法读取：{error}')]) from error
                sources.append(dict(ref=item['ref'], path=candidate.as_posix(), commit=source['commit'],
                                    sha256=digest(raw), confirmed_by=item['confirmed_by'], content=content))
                break
        if sources:
            push['sop_sources'] = sources
        self.request(self.api + '/scenario-file', method='PUT', body=push)
        uploaded, results = set(), []
        for row in rows:
            evidence = []
            for artifact in row['evidence']:
                try:
                    raw = artifact.read_bytes()
                except OSError as error:
                    raise Invalid('scenario-results-invalid', [problem(f'证据 {artifact.name} 无法读取：{error}')]) from error
                sha = digest(raw)
                if sha not in uploaded:
                    self.request('/api/v1/evidence', method='POST', body=raw,
                                 headers={'X-Evidence-Name': quote(artifact.name, safe=''),
                                          'Content-Type': 'application/octet-stream'})
                    uploaded.add(sha)
                evidence.append(dict(name=artifact.name, sha256=sha))
            results.append(dict(row, fingerprint=fingerprints[row['scenario']], evidence=evidence))
        payload = dict(idempotency_key=digest((scenario_sha + digest(results_bytes)).encode('ascii')),
                       scenario_file_sha256=scenario_sha, product=dict(commit=source['commit'],
                       digest=source['product_fingerprint'], dirty=source['dirty']),
                       submitted_by=pushed_by, results=results)
        if implementer is not None:
            payload['implementer'] = implementer
        self.assert_current(path, entry_path, scenario_sha, source)
        response = self.request(self.api + '/rounds', method='POST', body=payload)
        return dict(round=response['round'], statistics=response['statistics'],
                    **self.pending(scenarios, fingerprints, source))
