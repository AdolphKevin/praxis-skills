"""Input contracts and line-aware validation for SOP-VERIFY-1."""
from __future__ import annotations

import json
from pathlib import Path

from _yaml import Mapping, loads


class Invalid(Exception):
    def __init__(self, code, problems):
        self.code = code
        self.problems = problems
        super().__init__(code)


def problem(message, line=None):
    return {'line': line, 'problem': message}


def load_document(path, code, raw=None):
    try:
        return loads(raw.decode('utf-8') if raw is not None else path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as error:
        raise Invalid(code, [problem(str(error), getattr(error, 'lineno', None))]) from error


def line_of(value, key=None):
    return getattr(value, 'lines', {}).get(key, getattr(value, 'line', 1))


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, nonempty=True):
    return (isinstance(value, list) and (bool(value) or not nonempty)
            and all(text(item) for item in value))


class Validator:
    def __init__(self):
        self.problems = []

    def add(self, value, key, message):
        self.problems.append(problem(message, line_of(value, key)))

    def fields(self, value, required, optional, label):
        if not isinstance(value, dict):
            self.add(value, None, f'{label} 必须是对象')
            return False
        for key in required:
            if key not in value:
                self.add(value, None, f'{label} 缺少 {key}')
        for key in value:
            if key not in required | optional:
                self.add(value, key, f'{label} 格式外字段 {key}')
        return True

    def texts(self, value, keys, label):
        for key in keys:
            if not text(value.get(key)):
                self.add(value, key, f'{label} 的 {key} 必须是非空字符串')

    def arrays(self, value, keys, label, nonempty=True):
        for key in keys:
            if not strings(value.get(key), nonempty):
                self.add(value, key, f'{label} 的 {key} 必须是字符串数组'
                         + ('且非空' if nonempty else ''))

    def finish(self, code):
        if self.problems:
            raise Invalid(code, self.problems)


class JsonValidator(Validator):
    """JSON decoded without source marks is located by path, not guessed line."""
    def __init__(self):
        super().__init__()
        self.path = ''

    def add(self, value, key, message):
        location = self.path
        if key is not None:
            location += ('.' if location else '') + str(key)
        self.problems.append(problem(f'{location or "$"}：{message}'))


ENTRY_REQUIRED = {'surface', 'operate', 'observe', 'evidence', 'isolation'}
ENTRY_FIELDS = ENTRY_REQUIRED | {'address_env', 'candidate', 'start', 'reload'}
CHECK_FIELDS = {'argv', 'cwd', 'timeout', 'format', 'report', 'required_env'}
CHECK_METADATA = {'purpose', 'required_cases', 'environment', 'coverage', 'artifacts',
                  'review', 'repository', 'revision_sensitive'}
NEGATIVE_TYPES = set('empty-input over-length not-found permission cross-tenant duplicate '
                     'concurrency disconnect timeout archived invalid-input incomplete-input '
                     'interrupted stale-input tampered-input other'.split())


def validate_entries(document):
    v = Validator()
    if v.fields(document, {'entries'}, {'checks'}, '入口声明'):
        entries = document.get('entries')
        if not isinstance(entries, dict) or not entries:
            v.add(document, 'entries', 'entries 必须是非空对象')
        else:
            for name, entry in entries.items():
                if not text(name):
                    v.add(entries, name, '入口名必须是非空字符串')
                if not isinstance(entry, dict):
                    v.add(entries, name, f'{name} 必须是对象')
                    continue
                if v.fields(entry, ENTRY_REQUIRED, ENTRY_FIELDS - ENTRY_REQUIRED, str(name)):
                    v.texts(entry, ['surface', 'operate', 'isolation'], str(name))
                    v.arrays(entry, ['observe', 'evidence'], str(name))
                    if 'address_env' in entry:
                        import re
                        if not isinstance(entry['address_env'], str) or not re.fullmatch(
                                r'[A-Za-z_][A-Za-z0-9_]*', entry['address_env']):
                            v.add(entry, 'address_env', f'{name} 的 address_env 必须是环境变量名')
                    if 'candidate' in entry and entry['candidate'] not in ('checkout', 'start', 'in-place'):
                        v.add(entry, 'candidate', f'{name} 的 candidate 必须是 checkout、start 或 in-place')
                    if entry.get('candidate') == 'start' and 'address_env' not in entry:
                        v.add(entry, 'candidate', f'{name} 的 candidate 为 start 时必须填写 address_env')
                    for key in ('start', 'reload'):
                        if key in entry or (key == 'start' and entry.get('candidate') == 'start'):
                            v.arrays(entry, [key], str(name))
        checks = document.get('checks', {})
        if not isinstance(checks, dict):
            v.add(document, 'checks', 'checks 必须是对象')
        else:
            for name, check in checks.items():
                if not text(name):
                    v.add(checks, name, '检查编号必须是非空字符串')
                if not isinstance(check, dict):
                    v.add(checks, name, f'{name} 必须是对象')
                    continue
                if not v.fields(check, {'argv', 'timeout', 'format'},
                                (CHECK_FIELDS | CHECK_METADATA) - {'argv', 'timeout', 'format'}, str(name)):
                    continue
                v.arrays(check, ['argv'], str(name))
                if not isinstance(check.get('cwd', '.'), str):
                    v.add(check, 'cwd', f'{name} 的 cwd 必须是字符串')
                if type(check.get('timeout')) is not int or check['timeout'] <= 0:
                    v.add(check, 'timeout', f'{name} 的 timeout 必须是正整数')
                if check.get('format') not in ('junit', 'go-json'):
                    v.add(check, 'format', f'{name} 的 format 必须是 junit 或 go-json')
                if 'report' in check or check.get('format') == 'junit':
                    v.texts(check, ['report'], str(name))
                if 'required_env' in check:
                    v.arrays(check, ['required_env'], str(name), False)
    v.finish('entries-invalid')
    return document['entries']


def select_fields(value, fields):
    """Keep source positions when selecting the supported fields from tw JSON."""
    if not isinstance(value, dict):
        return value
    selected = Mapping(line_of(value))
    selected.update((key, val) for key, val in value.items() if key in fields)
    selected.lines = {key: line_of(value, key) for key in selected}
    return selected


def resolve_entries(root, scenario, explicit=None):
    config = root / '.tw/config.json'
    sibling = scenario.with_name('entries.yaml')
    selected = Path(explicit) if explicit else sibling if sibling.exists() else config
    if not selected.is_absolute():
        selected = root / selected
    if not selected.exists():
        if explicit:
            message = f'--entries 指定的入口文件不存在：{selected}'
        else:
            message = (f'未找到入口声明；未指定 --entries，已查找场景同目录的 entries.yaml：{sibling}；'
                       f'仓库 .tw/config.json 的 acceptance_entries：{config}')
        raise Invalid('entries-invalid', [problem(message)])
    doc = load_document(selected, 'entries-invalid')
    warnings = []
    if selected == config:
        raw = doc.get('acceptance_entries', {}) if isinstance(doc, dict) else {}
        checks = doc.get('checks', {}) if isinstance(doc, dict) else {}
        selected_entries = select_fields(raw, raw) if isinstance(raw, dict) else raw
        if isinstance(selected_entries, dict):
            for name in selected_entries:
                selected_entries[name] = select_fields(selected_entries[name], ENTRY_FIELDS)
        selected_doc = Mapping(line_of(doc))
        selected_doc.update(entries=selected_entries, checks=checks)
        selected_doc.lines = {'entries': line_of(doc, 'acceptance_entries'), 'checks': line_of(doc, 'checks')}
        doc = selected_doc
    entries = validate_entries(doc)
    if selected == sibling and config.exists():
        try:
            other_doc = json.loads(config.read_text(encoding='utf-8'))
            other = other_doc.get('acceptance_entries', {})
            for name, entry in entries.items():
                if name in other and isinstance(other[name], dict):
                    comparable = {k: val for k, val in other[name].items() if k in ENTRY_FIELDS}
                    if entry != comparable:
                        warnings.append(f'{name} 入口在 entries.yaml 与 .tw/config.json 中内容不同')
            other_checks = other_doc.get('checks', {})
            for name, check in doc.get('checks', {}).items():
                if name in other_checks and check != other_checks[name]:
                    warnings.append(f'{name} 检查在 entries.yaml 与 .tw/config.json 中内容不同')
        except (OSError, UnicodeError, ValueError, AttributeError):
            warnings.append('.tw/config.json 无法读取，已使用 entries.yaml')
    return doc, selected.resolve(), warnings


def validate_scenarios(doc, entries, checks=None):
    v = Validator()
    if not v.fields(doc, {'metadata', 'sops'}, set(), '场景文件'):
        v.finish('scenario-file-invalid')
    metadata = doc.get('metadata')
    if v.fields(metadata, {'requirement', 'batch', 'version', 'owner', 'sources'}, {'tags'}, 'metadata'):
        v.texts(metadata, ['requirement', 'batch', 'owner'], 'metadata')
        if not (text(metadata.get('version')) or type(metadata.get('version')) in (int, float)):
            v.add(metadata, 'version', 'metadata 的 version 必须有值')
        sources = metadata.get('sources')
        if not isinstance(sources, list) or not sources:
            v.add(metadata, 'sources', 'sources 必须是非空数组')
        else:
            for source in sources:
                if v.fields(source, {'ref', 'version', 'confirmed_by'}, set(), '来源'):
                    v.texts(source, ['ref', 'confirmed_by'], '来源')
                    if not (text(source.get('version')) or type(source.get('version')) in (int, float)):
                        v.add(source, 'version', '来源 version 必须有值')
        if 'tags' in metadata:
            v.arrays(metadata, ['tags'], 'metadata', False)
    nodes = doc.get('sops')
    if not isinstance(nodes, list) or not nodes:
        v.add(doc, 'sops', 'sops 必须是非空数组')
        v.finish('scenario-file-invalid')
    node_ids, scenario_ids, scenarios = set(), set(), []
    for node in nodes:
        if not v.fields(node, {'id', 'title', 'actor', 'entry', 'scenarios'},
                        {'must', 'negative_exempt'}, '节点'):
            continue
        label = str(node.get('id', '节点'))
        v.texts(node, ['id', 'title', 'actor', 'entry'], label)
        node_id = node.get('id')
        if text(node_id):
            if node_id in node_ids:
                v.add(node, 'id', f'节点编号重复 {node_id}')
            node_ids.add(node_id)
        if 'must' in node:
            v.arrays(node, ['must'], label)
        if 'negative_exempt' in node:
            v.texts(node, ['negative_exempt'], label)
        items = node.get('scenarios')
        if not isinstance(items, list) or not items:
            v.add(node, 'scenarios', f'{label} 的 scenarios 必须是非空数组')
            continue
        polarities = [s.get('polarity') for s in items if isinstance(s, dict)]
        if 'positive' not in polarities:
            v.add(node, 'scenarios', f'{label} 缺少 positive 场景')
        if 'negative' not in polarities and not text(node.get('negative_exempt')):
            v.add(node, 'scenarios', f'{label} 缺少 negative 场景或 negative_exempt')
        for s in items:
            required = {'id', 'polarity', 'title', 'actor', 'priority', 'verify',
                        'initial_state', 'steps', 'expected', 'forbidden_effects'}
            optional = {'negative_type', 'refs', 'evidence_hints', 'tags', 'regression'}
            if not v.fields(s, required, optional, str(s.get('id', label)) if isinstance(s, dict) else label):
                continue
            label_s = str(s.get('id', label))
            v.texts(s, ['id', 'title', 'actor', 'priority', 'verify'], label_s)
            ident = s.get('id')
            if text(ident):
                if ident in scenario_ids:
                    v.add(s, 'id', f'场景编号重复 {ident}')
                scenario_ids.add(ident)
            if s.get('polarity') not in ('positive', 'negative'):
                v.add(s, 'polarity', f'{label_s} 的 polarity 必须是 positive 或 negative')
            if s.get('polarity') == 'negative' and (not isinstance(s.get('negative_type'), str)
                                                     or s['negative_type'] not in NEGATIVE_TYPES):
                v.add(s, 'negative_type', f'{label_s} 的 negative_type 不合法或缺失')
            if isinstance(s.get('verify'), str) and s['verify'] not in entries:
                v.add(s, 'verify', f'{label_s} verify 引用未声明入口 {s["verify"]}')
            v.arrays(s, ['initial_state', 'steps', 'expected'], label_s)
            v.arrays(s, ['forbidden_effects'], label_s, False)
            for key in ('refs', 'evidence_hints', 'tags'):
                if key in s:
                    v.arrays(s, [key], label_s, False)
            if 'regression' in s:
                reg = s['regression']
                if not isinstance(reg, dict):
                    v.add(s, 'regression', f'{label_s} regression 必须是对象')
                elif set(reg) == {'check', 'cases'}:
                    v.texts(reg, ['check'], label_s)
                    v.arrays(reg, ['cases'], label_s)
                    if text(reg.get('check')) and reg['check'] not in (checks or {}):
                        v.add(reg, 'check', f'{label_s} regression.check 引用未声明检查 {reg["check"]}')
                elif set(reg) == {'manual', 'owner', 'trigger'}:
                    v.texts(reg, ['manual', 'owner', 'trigger'], label_s)
                elif set(reg) == {'pending'}:
                    v.texts(reg, ['pending'], label_s)
                else:
                    v.add(s, 'regression', f'{label_s} regression 字段组合不合法')
            scenarios.append(s)
    v.finish('scenario-file-invalid')
    return scenarios


def load_results(path, scenario_ids, raw=None):
    from datetime import datetime, timezone
    v = Validator()
    try:
        lines = (path.read_text(encoding='utf-8') if raw is None else raw.decode('utf-8')).splitlines()
    except (OSError, UnicodeError) as error:
        raise Invalid('scenario-results-invalid', [problem(str(error))]) from error
    if not any(line.strip() for line in lines):
        raise Invalid('scenario-results-invalid', [problem('结果文件至少填写一条场景结果', 1)])
    seen, rows = set(), []
    for number, line in enumerate(lines, 1):
        start = len(v.problems)
        try:
            row = json.loads(line)
        except ValueError as error:
            v.problems.append(problem(f'JSON 无法解析: {error}', number))
            continue
        if not v.fields(row, {'scenario', 'status', 'actual', 'evidence', 'executed_at', 'executor'},
                        {'session', 'finding', 'note'}, '结果'):
            v.problems[-1]['line'] = number
            continue
        v.texts(row, ['scenario', 'status', 'actual', 'executed_at', 'executor'], '结果')
        for key in ('session', 'finding', 'note'):
            if key in row and not isinstance(row[key], str):
                v.add(row, key, f'{key} 必须是字符串')
        ident = row.get('scenario')
        if isinstance(ident, str):
            if ident not in scenario_ids:
                v.add(row, 'scenario', f'不存在的场景 {ident}')
            if ident in seen:
                v.add(row, 'scenario', f'场景重复 {ident}')
            seen.add(ident)
        status = row.get('status')
        if status not in ('pass', 'fail', 'blocked', 'skip'):
            v.add(row, 'status', 'status 必须是 pass、fail、blocked 或 skip')
        if status in ('blocked', 'skip') and not text(row.get('finding')):
            v.add(row, 'finding', f'{status} 必须填写 finding')
        stamp = row.get('executed_at')
        try:
            if not isinstance(stamp, str):
                raise ValueError('必须是 ISO 8601 字符串')
            stamp = datetime.fromisoformat(stamp[:-1] + '+00:00' if stamp.endswith('Z') else stamp)
            if stamp.utcoffset() is None:
                raise ValueError('必须包含时区')
            if stamp > datetime.now(timezone.utc):
                raise ValueError('不能晚于当前时间')
        except (ValueError, OverflowError) as error:
            v.add(row, 'executed_at', f'executed_at {error}')
        paths = row.get('evidence')
        resolved = []
        if not isinstance(paths, list) or not all(text(p) for p in paths):
            v.add(row, 'evidence', 'evidence 必须是路径字符串数组')
        else:
            if status in ('pass', 'fail') and not paths:
                v.add(row, 'evidence', f'{status} 至少需要一项 evidence')
            for name in paths:
                candidate = Path(name)
                try:
                    target = (path.parent / candidate).resolve()
                    if candidate.is_absolute() or not target.is_relative_to(path.parent.resolve()):
                        raise ValueError('证据路径越出结果文件目录')
                    if not target.is_file():
                        raise ValueError('证据文件不存在或不是普通文件')
                    if target.stat().st_size > 64 * 1024 * 1024:
                        raise ValueError('证据文件超过 64 MiB')
                    resolved.append(target)
                except (OSError, ValueError, RuntimeError) as error:
                    v.add(row, 'evidence', f'{name}: {error}')
        for item in v.problems[start:]:
            item['line'] = number
        rows.append(dict(row, evidence=resolved))
    v.finish('scenario-results-invalid')
    return rows


def validate_cases(doc):
    v = Validator()
    if not isinstance(doc, dict) or len({'test_cases', 'cases'} & doc.keys()) != 1:
        raise Invalid('cases-invalid', [problem('顶层必须包含 test_cases 或 cases 数组', line_of(doc))])
    key = 'test_cases' if 'test_cases' in doc else 'cases'
    items = doc[key]
    if not isinstance(items, list):
        raise Invalid('cases-invalid', [problem(f'{key} 必须是数组', line_of(doc, key))])
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            v.add(item, None, '用例必须是对象')
            continue
        v.texts(item, ['id', 'title'], '用例')
        ident = item.get('id')
        if text(ident):
            if ident in seen:
                v.add(item, 'id', f'重复用例编号 {ident}')
            seen.add(ident)
    v.finish('cases-invalid')
    return items


def evaluate_coverage(pairs, cases, scenario_ids):
    v = JsonValidator()
    case_ids = {item['id'] for item in cases}
    occurrences = {ident: 0 for ident in case_ids}
    conflicts = set()
    if v.fields(pairs, {'covered', 'conflict', 'disposed'}, set(), '配对文件'):
        for category in ('covered', 'conflict', 'disposed'):
            v.path = ''
            values = pairs.get(category)
            if not isinstance(values, list):
                v.add(pairs, category, f'{category} 必须是数组')
                continue
            for index, item in enumerate(values):
                v.path = f'{category}[{index}]'
                fields = {'case', 'state', 'reason', 'confirmed_by'} if category == 'disposed' else {'case', 'scenarios', 'note'}
                if not v.fields(item, fields, set(), category):
                    continue
                ident = item.get('case')
                v.texts(item, ['case'], category)
                if isinstance(ident, str):
                    if ident in occurrences:
                        occurrences[ident] += 1
                    else:
                        v.add(item, 'case', f'未导入的用例 {ident}')
                    if category == 'conflict':
                        conflicts.add(ident)
                if category == 'disposed':
                    v.texts(item, ['reason', 'confirmed_by'], str(ident))
                    if item.get('state') not in ('blocked', 'deferred', 'out-of-scope'):
                        v.add(item, 'state', f'{ident} 的 state 不合法')
                else:
                    v.arrays(item, ['scenarios'], str(ident))
                    if not isinstance(item.get('note'), str):
                        v.add(item, 'note', f'{ident} 的 note 必须是字符串')
                    if isinstance(item.get('scenarios'), list):
                        for scenario_index, scenario in enumerate(item['scenarios']):
                            if not isinstance(scenario, str) or scenario not in scenario_ids:
                                v.add(item, f'scenarios[{scenario_index}]', f'用例 {ident} 引用不存在的场景 {scenario}')
    missing = sorted(ident for ident, count in occurrences.items() if not count)
    duplicate = sorted(ident for ident, count in occurrences.items() if count > 1)
    for label, identifiers in [('遗漏', missing), ('重复归类', duplicate), ('冲突', sorted(conflicts))]:
        for ident in identifiers:
            v.problems.append(problem(f'$：{label}: {ident}'))
    complete = not v.problems
    result = dict(ok=complete, complete=complete, total=len(case_ids), missing=missing,
                  duplicate=duplicate, conflict=sorted(conflicts))
    if not complete:
        result.update(error_code='scenario-coverage-incomplete', problems=v.problems)
    return result
