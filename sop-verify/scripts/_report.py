"""One report model shared by Markdown and JSON rendering."""
from __future__ import annotations

from pathlib import Path
import re

from _state import now, ratio
from _yaml import comment_lines


def build_report(metadata, scenarios, fingerprints, state, source, scenario_text):
    rounds = state.rounds()
    groups = state.pending(scenarios, fingerprints, source)
    current = {p['scenario']: p['reason'] for p in groups['pending']}
    current.update({p['scenario']: 'guarded' for p in groups['guarded']})
    current.update({p['scenario']: p['status'] for p in groups['blocked']})
    rows, first_statuses = [], []
    declarations = dict(check=[], manual=[], pending=[])
    for scenario in scenarios:
        ident = scenario['id']
        history = [(r, row) for r in rounds for row in r['results']
                   if row['scenario'] == ident and row['content_fingerprint'] == fingerprints[ident]]
        latest = dict(history[-1][1], round=history[-1][0]['round']) if history else None
        rows.append(dict(id=ident, polarity=scenario['polarity'],
                         current_status=current.get(ident, 'pass'), latest_result=latest))
        if history:
            first_statuses.append(history[0][1]['status'])
        declaration = scenario.get('regression', {'pending': '未声明'})
        category = next(k for k in declarations if k in declaration)
        declarations[category].append(dict(scenario=ident, **declaration))
    first_rate = ratio(first_statuses.count('pass'), sum(s in ('pass', 'fail') for s in first_statuses))
    unconfirmed = []
    for line, text in comment_lines(scenario_text):
        match = re.match(r'^\s*#\s*待确认\s+([^：:\s]+)\s*[：:]\s*(.*)$', text)
        if match:
            unconfirmed.append(dict(id=match[1], content=match[2], line=line))
    return dict(ok=True, header=dict(batch=metadata['batch'], requirement=metadata['requirement'],
                                     sources=metadata['sources'], **source, generated_at=now()),
                scenarios=rows, rounds=[dict(round=r['round'], statistics=r['statistics']) for r in rounds],
                first_pass_rate=first_rate,
                regression=dict(counts={k: len(v) for k, v in declarations.items()}, details=declarations),
                unconfirmed=unconfirmed, unverified=groups['blocked'])


def rate_text(value):
    return f"{value['numerator']}/{value['denominator']}" if value['denominator'] else '无数据'


def cell(value):
    return str(value if value is not None else '—').replace('|', '\\|').replace('\r', '').replace('\n', '<br>')


def table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
            *['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows]]


def markdown(report):
    header = report['header']
    lines = ['# SOP 验证报告', '', '## 头部', '', f"批次：{header['batch']}",
             f"需求：{header['requirement']}", f"产品提交号：{header['commit'] or '尚无提交'}",
             f"产品指纹：{header['product_fingerprint']}", f"生成时间：{header['generated_at']}"]
    lines.extend(f"来源：{s['ref']}；版本：{s['version']}；确认人：{s['confirmed_by']}" for s in header['sources'])
    lines += ['', '## 场景表', '']
    values = []
    for row in report['scenarios']:
        latest = row['latest_result'] or {}
        evidence = '；'.join(f"{Path(e['path']).name} ({e['sha256'][:12]})" for e in latest.get('evidence', []))
        values.append([row['id'], row['polarity'], row['current_status'], latest.get('status'),
                       latest.get('executor'), latest.get('independence'), latest.get('actual'),
                       evidence, latest.get('finding', '')])
    lines += table(['编号', '极性', '当前状态', '最新结果', '执行者', '独立性', '实际结果', '证据与指纹前12位', 'finding'], values)
    lines += ['', '## 轮次表', '']
    if not report['rounds']:
        lines += ['尚无执行记录。', '']
    lines += table(['轮次', '执行数', 'pass', 'fail', 'blocked', 'skip', '通过率'],
                   [[row['round'], row['statistics']['executed'],
                     *[row['statistics'][s] for s in ('pass', 'fail', 'blocked', 'skip')],
                     rate_text(row['statistics']['pass_rate'])] for row in report['rounds']])
    lines += ['', '## 一次通过率', '', rate_text(report['first_pass_rate']), '', '## 回归声明', '']
    for category, count in report['regression']['counts'].items():
        lines += [f'{category}: {count}', '']
        for declaration in report['regression']['details'][category]:
            fields = '；'.join(f'{key}: {value}' for key, value in declaration.items() if key != 'scenario')
            lines.append(f"- {declaration['scenario']}：{fields}")
        lines.append('')
    lines += ['## 待确认预期', '']
    lines += [f"- {item['id']}（行 {item['line']}）：{item['content']}" for item in report['unconfirmed']] or ['无。']
    lines += ['', '## 未验证范围', '']
    lines += [f"- {item['scenario']}：{item['status']}；{item['finding']}" for item in report['unverified']] or ['无。']
    return '\n'.join(lines) + '\n'
