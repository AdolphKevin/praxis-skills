#!/usr/bin/env python3
"""核对 SOP 场景、登记本机执行结果并生成报告（Python 3.10 以上）。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from _state import State, product, now, repository_root
from _report import build_report, markdown, rate_text
from _board import Board, redact
from _pull import pull
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
    if 'items' in result:
        return render_status(result)
    lines = list(result.get('warnings', []))
    if 'scenario_sha256' in result:
        lines.append('场景文件 sha256：' + result['scenario_sha256'])
    lines += [f'{ident}: {value}' for ident, value in result.get('fingerprints', {}).items()]
    if 'round' in result:
        stats = result['statistics']
        if 'executed' in stats:
            lines.append(f"第 {result['round']} 轮；执行数 {stats['executed']}；"
                         + '；'.join(f'{key} {stats[key]}' for key in ('pass', 'fail', 'blocked', 'skip'))
                         + '；通过率 ' + rate_text(stats['pass_rate']))
        else:
            lines.append(f"第 {result['round']} 轮")
            for key, label in [('agent_pass_rate', '自动执行通过率'), ('manual_pass_rate', '人工复测通过率'),
                               ('retest_coverage', '复测覆盖率'), ('first_pass_rate', '一次通过率'),
                               ('executed_progress', '已执行进度'), ('reviewed_progress', '已复核进度')]:
                if key in stats:
                    lines.append(label + '：' + rate_text(stats[key]))
    for key, title in [('pending', '待执行'), ('guarded', '由回归守护'), ('blocked', '受阻')]:
        if key in result:
            lines.append(title + '：' + ('无' if not result[key] else ''))
            for item in result[key]:
                lines.append(item['scenario'] + ': ' + '；'.join(str(v) for k, v in item.items() if k != 'scenario'))
    if 'added' in result:
        lines.append('；'.join(f'{title} {result[key]}' for key, title in
                              [('added', '新增'), ('updated', '更新'), ('unchanged', '未变'), ('total', '并集')]))
    if 'upload' in result:
        lines.append(f"看板上传序号 {result['upload']}；用例并集 {result['union_count']} 条")
    if 'complete' in result:
        lines.append(f"覆盖完整；用例 {result['total']} 条")
    if 'board_url' in result:
        lines.append('批次页面：' + result['board_url'])
    if 'task' in result:
        lines.append(f"合并任务 {result['task']}；对应关系 {result['pairs_count']} 条")
        lines.extend('写入：' + name for name in result['written'])
    return '\n'.join(lines)


def render_status(result):
    if result['board'] is None:
        return '未配置看板（SOP_BOARD_URL），没有看板上的待处理事项'
    if result.get('warnings'):
        return '\n'.join(result['warnings'])
    if not result['items']:
        return '看板上没有待开发者处理的事项'
    titles = {'developer-action': '待开发者处理', 'developer-merge': '待开发者合入',
              'commit-needed': '待提交', 'cases-needed': '待补充', 'sync-needed': '待同步',
              'jira-manual': 'Jira 状态待人工更新', 'interrupted': '已中断'}
    groups = {}
    for item in result['items']:
        groups.setdefault(item['kind'], []).append(item)
    order = [kind for kind in titles if kind in groups] + [kind for kind in groups if kind not in titles]
    lines = []
    for kind in order:
        lines.append(titles.get(kind, kind))
        for item in groups[kind]:
            lines.append(f"  批次：{item.get('batch') or '项目级'}；任务：{item['task']}")
            lines.append('    原因：' + item['reason'])
            lines.append('    看板：' + item['url'])
            if item.get('resume'):
                lines.append('    接续：' + item['resume'])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', help='Git 仓库路径；默认使用当前目录所在仓库')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    commands = parser.add_subparsers(dest='command', required=True)
    descriptions = [
        ('status', '列出看板上待开发者处理的事项'),
        ('check', '核对场景文件与入口'), ('pending', '列出待执行场景'),
        ('submit', '登记结果并复制证据'), ('import-cases', '导入测试用例并保存并集'),
        ('coverage', '核对用例与场景的配对'), ('report', '输出验证报告'),
        ('pull', '取回看板的合并结果'),
    ]
    for name, description in descriptions:
        command = commands.add_parser(name, help=description)
        if name != 'status':
            command.add_argument('scenario', help='场景文件；相对路径从仓库根目录解析')
        if name == 'check':
            command.add_argument('--entries')
        if name == 'coverage':
            command.add_argument('--pairs', required=True)
        if name == 'pull':
            command.add_argument('--pairs')
            command.add_argument('--batch', help='场景文件尚不存在时的批次名')
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
        root = repository_root(args.root or '.')
        if args.command == 'status':
            result = (Board(root).status() if os.environ.get('SOP_BOARD_URL')
                      else dict(ok=True, board=None, items=[]))
            return output(args, result)
        path = (root / args.scenario).resolve()
        if not path.is_relative_to(root):
            raise Invalid('scenario-file-invalid', [problem('场景文件必须在仓库内')])
        if args.command == 'pull':
            pairs_path = (root / args.pairs).resolve() if args.pairs else None
            if pairs_path is not None and pairs_path.is_relative_to(root):
                parser.error('pull --pairs 必须指向仓库外路径')
            if not path.exists() and not args.batch:
                parser.error('场景文件尚不存在时必须用 --batch 指定批次')
            if args.batch and path.exists():
                document = load_document(path, 'scenario-file-invalid')
                metadata = document.get('metadata', {}) if isinstance(document, dict) else {}
                if isinstance(metadata, dict) and metadata.get('batch') != args.batch:
                    parser.error('--batch 与场景文件的 metadata.batch 不同')
            return output(args, pull(root, path, args.batch, pairs_path))
        try:
            scenario_bytes = path.read_bytes()
        except OSError as error:
            raise Invalid('scenario-file-invalid', [problem(str(error))]) from error
        data = load_document(path, 'scenario-file-invalid', scenario_bytes)
        entry_document, entry_path, warnings = resolve_entries(root, path, getattr(args, 'entries', None))
        scenarios = validate_scenarios(data, entry_document['entries'], entry_document.get('checks'))
        result = dict(ok=True, scenario_sha256=digest(scenario_bytes), warnings=warnings,
                      fingerprints={s['id']: content_fingerprint(s) for s in scenarios})
        if args.command == 'report':
            if os.environ.get('SOP_BOARD_URL'):
                response = Board(root, data['metadata']['batch']).report(args.format)
                result = response if args.format == 'json' else dict(ok=True, board_markdown=response)
            else:
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
            items = validate_cases(cases_doc)
            uploaded = (Board(root, data['metadata']['batch']).import_cases(cases_path)
                        if os.environ.get('SOP_BOARD_URL') else {})
            result.update(state.import_cases(cases_path, cases_doc, items))
            result.update(uploaded)
        if args.command in ('pending', 'submit') and os.environ.get('SOP_BOARD_URL'):
            board = Board(root, data['metadata']['batch'])
            state = State(root, path, data['metadata']['batch'])
            source = product(root, path, entry_path)
            if args.command == 'pending':
                result.update(board.pending(scenarios, result['fingerprints'], source))
            else:
                results_path = root / args.results
                try:
                    results_bytes = results_path.read_bytes()
                except OSError as error:
                    raise Invalid('scenario-results-invalid', [problem(str(error))]) from error
                rows = load_results(results_path, result['fingerprints'], results_bytes)
                result.update(board.submit(path, scenario_bytes, data, entry_document, entry_path,
                                           scenarios, result['fingerprints'], source, rows, results_bytes,
                                           args.implementer))
                state.bind()
            result['warnings'] = warnings + result.get('warnings', [])
        elif args.command in ('pending', 'submit'):
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
    except Invalid as error:
        result = dict(ok=False, error_code=error.code, problems=error.problems)
    return output(args, result)


def output(args, result):
    if os.environ.get('SOP_BOARD_URL'):
        result = redact(result)
    if args.command == 'report' and args.format != 'json' and result['ok']:
        for warning in result.get('warnings', []):
            print(warning)
        print(result['board_markdown'] if 'board_markdown' in result else markdown(result), end='')
    elif args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result['ok']:
        print(render_text(result))
    else:
        print(result['error_code'])
        for item in result['problems']:
            if item.get('line') is None:
                print(item['problem'])
            else:
                print(f"第 {item['line']} 行：{item['problem']}")
    if not result['ok']:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
