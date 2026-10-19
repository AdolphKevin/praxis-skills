#!/usr/bin/env python3
"""核对 SOP 场景、登记本机执行结果并生成报告（Python 3.10 以上）。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

from _state import State, product, now
from _report import build_report, markdown, rate_text
from _contracts import (
    Invalid, problem, load_document, resolve_entries, validate_scenarios,
    load_results, validate_cases, evaluate_coverage,
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def content_fingerprint(scenario):
    value = {k: [s.replace('\r\n', '\n').replace('\r', '\n') for s in scenario[k]]
             for k in ('initial_state', 'steps', 'expected', 'forbidden_effects')}
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':')).encode('utf-8'))


def render_text(result):
    lines = list(result.get('warnings', []))
    if 'scenario_sha256' in result:
        lines.append('场景文件 sha256：' + result['scenario_sha256'])
    lines += [f'{ident}: {value}' for ident, value in result.get('fingerprints', {}).items()]
    if 'round' in result:
        stats = result['statistics']
        lines.append(f"第 {result['round']} 轮；执行数 {stats['executed']}；"
                     + '；'.join(f'{key} {stats[key]}' for key in ('pass', 'fail', 'blocked', 'skip'))
                     + '；通过率 ' + rate_text(stats['pass_rate']))
    for key, title in [('pending', '待执行'), ('guarded', '由回归守护'), ('blocked', '受阻')]:
        if key in result:
            lines.append(title + '：' + ('无' if not result[key] else ''))
            for item in result[key]:
                lines.append(item['scenario'] + ': ' + '；'.join(str(v) for k, v in item.items() if k != 'scenario'))
    if 'added' in result:
        lines.append('；'.join(f'{title} {result[key]}' for key, title in
                              [('added', '新增'), ('updated', '更新'), ('unchanged', '未变'), ('total', '并集')]))
    if 'complete' in result:
        lines.append(f"覆盖完整；用例 {result['total']} 条")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', help='Git 仓库路径；默认使用当前目录所在仓库')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    commands = parser.add_subparsers(dest='command', required=True)
    descriptions = [
        ('check', '核对场景文件与入口'), ('pending', '列出待执行场景'),
        ('submit', '登记结果并复制证据'), ('import-cases', '导入测试用例并保存并集'),
        ('coverage', '核对用例与场景的配对'), ('report', '输出验证报告'),
    ]
    for name, description in descriptions:
        command = commands.add_parser(name, help=description)
        command.add_argument('scenario', help='场景文件；相对路径从仓库根目录解析')
        if name == 'check':
            command.add_argument('--entries')
        if name == 'coverage':
            command.add_argument('--pairs', required=True)
        if name == 'import-cases':
            command.add_argument('cases')
        if name == 'submit':
            command.add_argument('--results', required=True)
            command.add_argument('--implementer')
        command.add_argument('--root', default=argparse.SUPPRESS, help='指定 Git 仓库路径')
        formats = ('markdown', 'json') if name == 'report' else ('text', 'json')
        command.add_argument('--format', choices=formats, default=argparse.SUPPRESS,
                             help='输出格式；report 默认 markdown，其他命令默认 text')
    args = parser.parse_args()
    try:
        process = subprocess.run(['git', '--no-optional-locks', '-C', args.root or '.', 'rev-parse', '--show-toplevel'],
                                 capture_output=True, text=True)
        if process.returncode:
            raise Invalid('not-a-git-repository', [problem('不在 Git 仓库中')])
        root = Path(process.stdout.strip()).resolve()
        path = (root / args.scenario).resolve()
        if not path.is_relative_to(root):
            raise Invalid('scenario-file-invalid', [problem('场景文件必须在仓库内')])
        try:
            scenario_bytes = path.read_bytes()
        except OSError as error:
            raise Invalid('scenario-file-invalid', [problem(str(error))]) from error
        data = load_document(path, 'scenario-file-invalid', scenario_bytes)
        entries, entry_path, warnings = resolve_entries(root, path, getattr(args, 'entries', None))
        scenarios = validate_scenarios(data, entries)
        result = dict(ok=True, scenario_sha256=digest(scenario_bytes), warnings=warnings,
                      fingerprints={s['id']: content_fingerprint(s) for s in scenarios})
        if args.command == 'report':
            state = State(root, path, data['metadata']['batch'])
            result = build_report(data['metadata'], scenarios, result['fingerprints'], state,
                                  product(root, path, entry_path), scenario_bytes.decode('utf-8'))
            result['warnings'] = warnings
        if args.command == 'coverage':
            state = State(root, path, data['metadata']['batch'])
            pairs_path = (root / args.pairs).resolve()
            try:
                pairs = json.loads(pairs_path.read_text(encoding='utf-8'))
            except (OSError, UnicodeError, ValueError) as error:
                raise Invalid('scenario-coverage-incomplete', [problem(str(error))]) from error
            conclusion = evaluate_coverage(pairs, state.cases(), result['fingerprints'])
            state.save_snapshot('coverage', dict(recorded_at=now(), pairs=pairs, conclusion=conclusion))
            result.update(conclusion)
        if args.command == 'import-cases':
            state = State(root, path, data['metadata']['batch'])
            cases_path = (root / args.cases).resolve()
            cases_doc = load_document(cases_path, 'cases-invalid')
            result.update(state.import_cases(cases_path, cases_doc, validate_cases(cases_doc)))
        if args.command in ('pending', 'submit'):
            state = State(root, path, data['metadata']['batch'])
            source = product(root, path, entry_path)
            if args.command == 'submit':
                results_path = Path(args.results)
                if not results_path.is_absolute():
                    results_path = root / results_path
                rows = load_results(results_path, result['fingerprints'])
                pending = state.pending(scenarios, result['fingerprints'], source)['pending']
                missing = {p['scenario'] for p in pending} - {row['scenario'] for row in rows}
                if missing:
                    raise Invalid('scenario-results-incomplete', [problem('缺少场景 ' + ident)
                                                                  for ident in sorted(missing)])
                record = state.submit(path, rows, result['fingerprints'], source, args.implementer,
                                      result['scenario_sha256'], entry_path)
                result.update(round=record['round'], statistics=record['statistics'])
            result.update(state.pending(scenarios, result['fingerprints'], source))
    except (OSError, ValueError) as error:
        result = dict(ok=False, error_code='source-stale', problems=[problem(str(error))])
    except Invalid as error:
        result = dict(ok=False, error_code=error.code, problems=error.problems)
    if args.command == 'report' and args.format != 'json' and result['ok']:
        for warning in result.get('warnings', []):
            print(warning)
        print(markdown(result), end='')
    elif args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result['ok']:
        print(render_text(result))
    else:
        print(result['error_code'])
        for item in result['problems']:
            if item['line'] is None:
                print(item['problem'])
            else:
                print(f"第 {item['line']} 行：{item['problem']}")
    if not result['ok']:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
