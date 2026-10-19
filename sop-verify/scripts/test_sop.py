"""Public CLI contracts from SOP-VERIFY-1 revision 1 (I1, D1, D2)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().with_name('sop.py')


def fingerprint(scenario):
    # Independent reference calculation: build the exact D1 document explicitly.
    fields = ('initial_state', 'steps', 'expected', 'forbidden_effects')
    document = {key: [s.replace('\r\n', '\n').replace('\r', '\n')
                      for s in scenario[key]] for key in fields}
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def example():
    nodes = []
    for n in (1, 2):
        scenarios = []
        for polarity, suffix in (('positive', 'P'), ('negative', 'N')):
            scenario = dict(id=f'N{n}-{suffix}', polarity=polarity, title='核对中文',
                            actor='用户', priority='P0', verify='cli',
                            initial_state=['已准备\r\n数据'], steps=['运行命令'],
                            expected=['得到结果\r且无误'], forbidden_effects=[])
            if polarity == 'negative':
                scenario['negative_type'] = 'invalid-input'
            scenarios.append(scenario)
        nodes.append(dict(id=f'N{n}', title='流程', actor='用户',
                          entry='运行命令', scenarios=scenarios))
    return dict(metadata=dict(requirement='演示需求', batch='demo', version=1,
                              owner='负责人', sources=[dict(ref='SOP', version='1',
                                                        confirmed_by='负责人')]),
                sops=nodes)


class SopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sop-cli-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'app.txt').write_text('version one\n')
        subprocess.run(['git', '-C', str(self.repo), 'add', 'app.txt'], check=True)
        self.state = self.base / 'state'
        self.env = dict(os.environ, XDG_STATE_HOME=str(self.state),
                        PYTHONDONTWRITEBYTECODE='1')
        self.env.pop('SOP_VERIFY_STATE', None)
        self.doc = example()
        self.scenario = self.repo / 'docs/sop/demo.yaml'
        self.scenario.parent.mkdir(parents=True)
        self.entry = dict(surface='cli', operate='运行命令', observe=['输出'],
                          evidence=['命令记录'], isolation='临时目录')
        self.entries = self.scenario.with_name('entries.yaml')
        self.write_json(self.entries, {'entries': {'cli': self.entry}})
        self.save()

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def save(self):
        self.write_json(self.scenario, self.doc)

    def files(self, root):
        return {str(p.relative_to(root)): p.read_bytes()
                for p in root.rglob('*') if p.is_file()}

    def run_cli(self, *args, code=0, fmt='json', cwd=None, readonly=False, writes_on_error=False):
        before = self.files(self.repo)
        state_root = Path(self.env.get('SOP_VERIFY_STATE', str(self.state)))
        state = self.files(state_root)
        command = [sys.executable, str(SCRIPT), *map(str, args)]
        if fmt:
            command += ['--format', fmt]
        result = subprocess.run(command, cwd=cwd or self.repo, env=self.env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(code, result.returncode,
                         f'{command}\n{result.stdout}\n{result.stderr}')
        self.assertEqual(before, self.files(self.repo), 'CLI changed repository files')
        if readonly or (code and not writes_on_error):
            self.assertEqual(state, self.files(state_root), 'unexpected state writes')
        return json.loads(result.stdout) if fmt == 'json' else result.stdout

    def test_check_fingerprints_from_subdirectory(self):
        """I1/D1; SOP-01-P01: check is read-only, root-relative paths."""
        result = self.run_cli('check', 'docs/sop/demo.yaml',
                              cwd=self.scenario.parent, readonly=True)
        self.assertTrue(result['ok'])
        self.assertEqual(hashlib.sha256(self.scenario.read_bytes()).hexdigest(),
                         result['scenario_sha256'])
        self.assertEqual({s['id']: fingerprint(s) for n in self.doc['sops']
                          for s in n['scenarios']}, result['fingerprints'])
        self.assertEqual({}, self.files(self.state))
        output = self.run_cli('check', self.scenario, fmt='text', readonly=True)
        self.assertIn(result['scenario_sha256'], output)
        for value in result['fingerprints'].values():
            self.assertIn(value, output)

    def test_input_errors_and_schema_lines(self):
        """I1/D1; SOP-01-N01/N02: malformed scenarios and absent Git."""
        result = self.run_cli('check', self.scenario, cwd=self.base, code=1)
        self.assertEqual('not-a-git-repository', result['error_code'])
        for mutate, phrase in (
            (lambda d: d['sops'][0]['scenarios'].pop(), 'N1'),
            (lambda d: d['sops'][0]['scenarios'][0].update(verify='browser'), 'browser'),
            (lambda d: d['sops'][0]['scenarios'][0].update(surprise=True), 'surprise'),
            (lambda d: d['sops'][0]['scenarios'][0].update(steps=[]), 'steps'),
            (lambda d: d['sops'][1].update(id='N1'), 'N1'),
            (lambda d: d['metadata'].update(sources=[]), 'sources'),
        ):
            with self.subTest(phrase=phrase):
                self.doc = example()
                mutate(self.doc)
                self.save()
                result = self.run_cli('check', self.scenario, code=1)
                self.assertEqual('scenario-file-invalid', result['error_code'])
                self.assertIn(phrase, str(result['problems']))
                self.assertTrue(all(p['line'] for p in result['problems']))
        self.doc = example()
        self.doc['sops'][0]['scenarios'].pop()
        self.doc['sops'][0]['negative_exempt'] = '该节点没有失败分支'
        self.save()
        self.run_cli('check', self.scenario, readonly=True)

    def test_entries_precedence_fallback_and_validation(self):
        """I1/D1; SOP-01-P02: explicit, sibling, then tw entries."""
        self.entries.unlink()
        result = self.run_cli('check', self.scenario, code=1)
        self.assertEqual('entries-invalid', result['error_code'])
        tw_entry = dict(self.entry, operate='另一入口', extra='ignored')
        self.write_json(self.repo / '.tw/config.json',
                        {'acceptance_entries': {'cli': tw_entry}})
        self.run_cli('check', self.scenario, readonly=True)
        self.write_json(self.entries, {'entries': {'cli': self.entry}})
        result = self.run_cli('check', self.scenario, readonly=True)
        self.assertIn('cli', str(result['warnings']))
        explicit = self.write_json(self.base / 'explicit.json',
                                   {'entries': {'cli': self.entry}})
        self.entries.write_text('invalid')
        self.run_cli('--root', self.repo, 'check', self.scenario,
                     '--entries', explicit, cwd=self.base, readonly=True)
        self.write_json(explicit, {'entries': {'cli': dict(self.entry, observe=[])}})
        result = self.run_cli('check', self.scenario, '--entries', explicit, code=1)
        self.assertEqual('entries-invalid', result['error_code'])
        self.assertTrue(result['problems'][0]['line'])

    def yaml_fixture(self):
        return """# 中文注释
metadata:
  requirement: 演示需求
  batch: demo
  version: 1
  owner: 负责人
  sources:
  - ref: SOP
    version: '1'
    confirmed_by: 负责人
sops:
- id: N1
  title: 流程
  actor: 用户
  entry: 运行命令
  scenarios:
  - id: N1-P
    polarity: positive
    title: '中文 ''引号''
      折行'
    actor: 用户
    priority: P0
    verify: cli
    initial_state:
    - 准备好的
      初始状态
    steps: ['运行,命令', "中文 # 内容"] # 尾注释
    expected:
    - "得到
      正确结果"
    - '有 ''单引号''
      的结果'
    - 普通的
      折叠结果

      下一段
    forbidden_effects: []
    tags: ["中文", 'a,b', 'it''s']
  - id: N1-N
    polarity: negative
    negative_type: invalid-input
    title: 反向
    actor: 用户
    priority: P1
    verify: cli
    initial_state: [准备]
    steps: [运行]
    expected: [拒绝]
    forbidden_effects: []
"""

    def test_yaml_folding_quotes_flow_and_comments(self):
        """D1: PyYAML-style indentationless sequences and folded scalars."""
        self.scenario.write_text(self.yaml_fixture(), encoding='utf-8')
        expected = dict(initial_state=['准备好的 初始状态'],
                        steps=['运行,命令', '中文 # 内容'],
                        expected=['得到 正确结果', "有 '单引号' 的结果", '普通的 折叠结果\n下一段'],
                        forbidden_effects=[])
        result = self.run_cli('check', self.scenario, readonly=True)
        self.assertEqual(fingerprint(expected), result['fingerprints']['N1-P'])
        self.entries.write_text("""entries:
  cli:
    surface: cli
    operate: '运行
      命令'
    observe: [输出]
    evidence: ['命令记录']
    isolation: 临时目录
""", encoding='utf-8')
        self.run_cli('check', self.scenario, readonly=True)

    def test_yaml_unsupported_features_report_exact_lines(self):
        """D1; SOP-01-N03: reject anchors, aliases, tags, blocks, documents."""
        original = self.yaml_fixture()
        for fragment in ('&steps [运行]', '*steps', '!tag [运行]', '|', '>',
                         '[运行, &x 引用]'):
            with self.subTest(fragment=fragment):
                content = original.replace('steps: [运行]', 'steps: ' + fragment)
                self.scenario.write_text(content, encoding='utf-8')
                expected_line = next(i for i, line in enumerate(content.splitlines(), 1)
                                     if 'steps: ' + fragment in line)
                result = self.run_cli('check', self.scenario, code=1)
                self.assertEqual('scenario-file-invalid', result['error_code'])
                self.assertEqual(expected_line, result['problems'][0]['line'])
        self.scenario.write_text(original + '---\nmetadata: {}\n')
        result = self.run_cli('check', self.scenario, code=1)
        self.assertEqual(len(original.splitlines()) + 1, result['problems'][0]['line'])
        self.scenario.write_text(original.replace('verify: cli', 'surprise: cli', 1))
        result = self.run_cli('check', self.scenario, code=1)
        self.assertIn(dict(line=23, problem='N1-P 格式外字段 surprise'), result['problems'])

    def test_pending_new_and_usage(self):
        """I1; SOP-02-P01: all four new, no state created; usage exits 2."""
        result = self.run_cli('pending', self.scenario, readonly=True)
        self.assertEqual({s['id']: 'new' for n in self.doc['sops'] for s in n['scenarios']},
                         {p['scenario']: p['reason'] for p in result['pending']})
        self.assertEqual([], result['guarded'])
        self.assertEqual([], result['blocked'])
        self.assertEqual({}, self.files(self.state))
        output = self.run_cli('check', code=2, fmt=None)
        self.assertEqual('', output)

    def results_file(self, statuses=None, executor='Li Si'):
        ids = [s['id'] for n in self.doc['sops'] for s in n['scenarios']]
        statuses = statuses or dict.fromkeys(ids, 'pass')
        folder = self.base / 'results'
        folder.mkdir(exist_ok=True)
        (folder / 'evidence.txt').write_text('真实证据\n', encoding='utf-8')
        rows = [dict(scenario=ident, status=status, actual='核对结果',
                     evidence=['evidence.txt'] if status in ('pass', 'fail') else [],
                     executed_at='2020-01-01T12:00:00+08:00', executor=executor,
                     **({'finding': 'Q1'} if status in ('blocked', 'skip') else {}))
                for ident, status in statuses.items()]
        path = folder / 'results.jsonl'
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
        return path

    def batch_path(self):
        root = self.repo.resolve()
        checkout = root.name + '-' + hashlib.sha256(str(root).encode()).hexdigest()[:12]
        base = Path(self.env.get('SOP_VERIFY_STATE', str(self.state / 'sop-verify')))
        return base / checkout / 'demo'

    def test_submit_round_evidence_statistics_and_independence(self):
        """I1/D2; SOP-03-P01/P02: real evidence, three independence labels."""
        path = self.results_file({'N1-P': 'pass', 'N1-N': 'fail',
                                 'N2-P': 'pass', 'N2-N': 'pass'})
        result = self.run_cli('submit', self.scenario, '--results', path,
                              '--implementer', 'Zhang San')
        self.assertEqual(1, result['round'])
        self.assertEqual(dict(executed=4, **{'pass': 3, 'fail': 1, 'blocked': 0, 'skip': 0},
                              pass_rate=dict(numerator=3, denominator=4, rate=.75)), result['statistics'])
        round_path = self.batch_path() / 'rounds/1/round.json'
        record = json.loads(round_path.read_text())
        self.assertEqual(1, record['data_version'])
        self.assertEqual('sop-round', record['kind'])
        self.assertEqual('demo', record['batch'])
        self.assertEqual('docs/sop/demo.yaml', record['scenario_file'])
        self.assertEqual(hashlib.sha256(self.scenario.read_bytes()).hexdigest(), record['scenario_sha256'])
        self.assertIsNone(record['commit'])  # No commits are created by this suite.
        self.assertTrue(record['dirty'])
        self.assertEqual('Zhang San', record['implementer'])
        self.assertIn('submitted_at', record)
        self.assertEqual(result['statistics'], record['statistics'])
        for row in record['results']:
            self.assertEqual('independent', row['independence'])
            self.assertEqual(fingerprint(self.doc['sops'][0]['scenarios'][0]), row['content_fingerprint'])
            artifact = row['evidence'][0]
            self.assertEqual(hashlib.sha256((path.parent / 'evidence.txt').read_bytes()).hexdigest(), artifact['sha256'])
            self.assertEqual((path.parent / 'evidence.txt').read_bytes(),
                             (round_path.parent / artifact['path']).read_bytes())
        self.assertEqual({'scenario_file': 'docs/sop/demo.yaml'},
                         json.loads((self.batch_path() / 'batch.json').read_text()))
        self.assertEqual([{'scenario': 'N1-N', 'reason': 'failed'}], result['pending'])
        path = self.results_file({'N1-N': 'pass'}, executor='  zhang  SAN ')
        self.run_cli('submit', self.scenario, '--results', path, '--implementer', 'Zhang San')
        second = json.loads((self.batch_path() / 'rounds/2/round.json').read_text())
        self.assertEqual('self-check', second['results'][0]['independence'])
        path = self.results_file({'N1-P': 'pass'}, executor='Wang Wu')
        self.run_cli('submit', self.scenario, '--results', path)
        third = json.loads((self.batch_path() / 'rounds/3/round.json').read_text())
        self.assertEqual('undeclared', third['results'][0]['independence'])

    def test_pending_changed_failed_blocked_and_product_changes(self):
        """I1/D2; SOP-02-P01/P02/N01/N02: current-content history."""
        self.doc['sops'][0]['scenarios'][0]['regression'] = dict(check='unit', cases=['Demo::test_a'])
        self.save()
        self.run_cli('submit', self.scenario, '--results', self.results_file())
        self.assertEqual([], self.run_cli('pending', self.scenario, readonly=True)['pending'])
        self.doc['sops'][0]['scenarios'][1]['expected'] = ['新的要求']
        self.save()
        self.assertEqual([dict(scenario='N1-N', reason='changed')],
                         self.run_cli('pending', self.scenario, readonly=True)['pending'])
        self.run_cli('submit', self.scenario, '--results', self.results_file({'N1-N': 'fail', 'N2-N': 'blocked'}))
        result = self.run_cli('pending', self.scenario, readonly=True)
        self.assertEqual([dict(scenario='N1-N', reason='failed')], result['pending'])
        self.assertEqual('Q1', result['blocked'][0]['finding'])
        (self.repo / 'app.txt').write_text('version two')
        result = self.run_cli('pending', self.scenario, readonly=True)
        self.assertEqual({'N1-N': 'failed', 'N2-P': 'source-changed'},
                         {p['scenario']: p['reason'] for p in result['pending']})
        self.assertEqual('N1-P', result['guarded'][0]['scenario'])
        self.assertIn('需确认该检查在当前源码通过', result['guarded'][0]['message'])

    def test_submit_empty_results_rejected_without_new_round(self):
        """W1; I1/D1: no result lines cannot create an empty round."""
        path = self.results_file()
        self.run_cli('submit', self.scenario, '--results', path)
        self.assertEqual([], self.run_cli('pending', self.scenario, readonly=True)['pending'])
        before = self.files(self.state)
        empty = path.with_name('empty.jsonl')
        for content in ('', '\n', '  \t\n \n'):
            with self.subTest(content=repr(content)):
                empty.write_text(content, encoding='utf-8')
                result = self.run_cli('submit', self.scenario, '--results', empty, code=1)
                self.assertEqual(dict(ok=False, error_code='scenario-results-invalid',
                                      problems=[dict(line=1, problem='结果文件至少填写一条场景结果')]),
                                 result)
        self.assertEqual(before, self.files(self.state))
        self.assertEqual(['1'], [p.parent.name for p in self.state.rglob('round.json')])

    def test_results_incomplete_and_invalid_line_numbers(self):
        """D1/I1; SOP-03-N01/N02: incomplete or invalid never writes state."""
        path = self.results_file({'N1-P': 'pass'})
        result = self.run_cli('submit', self.scenario, '--results', path, code=1)
        self.assertEqual('scenario-results-incomplete', result['error_code'])
        for ident in ('N1-N', 'N2-P', 'N2-N'):
            self.assertIn(ident, str(result['problems']))
        path = self.results_file()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['evidence'] = []
        rows[1]['evidence'] = ['../outside.txt']
        rows[2]['executed_at'] = '2020-01-01T00:00:00'
        rows[3].update(status='blocked', evidence=[])
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        result = self.run_cli('submit', self.scenario, '--results', path, code=1)
        self.assertEqual('scenario-results-invalid', result['error_code'])
        self.assertEqual({1, 2, 3, 4}, {p['line'] for p in result['problems']})
        output = self.run_cli('submit', self.scenario, '--results', path, code=1, fmt='text')
        for number in range(1, 5):
            self.assertIn(f'第 {number} 行：', output)
        self.assertEqual({}, self.files(self.state))

    def test_text_problems_without_line_preserve_json_null(self):
        """W2; I1: an unnumbered problem has no line prefix in text."""
        outside = self.base / 'outside.yaml'
        result = self.run_cli('check', outside, code=1)
        self.assertEqual(dict(ok=False, error_code='scenario-file-invalid',
                              problems=[dict(line=None, problem='场景文件必须在仓库内')]), result)
        output = self.run_cli('check', outside, code=1, fmt='text')
        self.assertEqual('scenario-file-invalid\n场景文件必须在仓库内\n', output)

    def test_text_problems_with_line_use_numbered_prefix(self):
        """W2; I1: text prints the actual line number; JSON stays numeric."""
        path = self.results_file()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['evidence'] = []
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        result = self.run_cli('submit', self.scenario, '--results', path, code=1)
        self.assertEqual(dict(ok=False, error_code='scenario-results-invalid',
                              problems=[dict(line=1, problem='pass 至少需要一项 evidence')]), result)
        output = self.run_cli('submit', self.scenario, '--results', path, code=1, fmt='text')
        self.assertEqual('scenario-results-invalid\n第 1 行：pass 至少需要一项 evidence\n', output)

    def test_results_reject_unknown_duplicate_time_and_unsafe_evidence(self):
        """D1: complete result contract, including symlink and size boundary."""
        outside = self.base / 'outside.txt'
        outside.write_text('outside')
        path = self.results_file()
        (path.parent / 'escape').symlink_to(outside)
        large = path.parent / 'large'
        with large.open('wb') as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        for changes in (dict(executed_at='2999-01-01T00:00:00Z'),
                        dict(status='unknown'), dict(scenario='unknown'),
                        dict(extra=True), dict(actual=''), dict(executor=''),
                        dict(evidence=['missing']), dict(evidence=['escape']),
                        dict(evidence=[str(outside)]), dict(evidence=['large']),
                        dict(status='skip', finding='')):
            with self.subTest(changes=changes):
                path = self.results_file()
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                rows[0].update(changes)
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                result = self.run_cli('submit', self.scenario, '--results', path, code=1)
                self.assertEqual('scenario-results-invalid', result['error_code'])
                self.assertEqual(1, result['problems'][0]['line'])
        path = self.results_file()
        path.write_text(path.read_text() + path.read_text().splitlines()[0] + '\n')
        result = self.run_cli('submit', self.scenario, '--results', path, code=1)
        self.assertEqual(5, result['problems'][0]['line'])
        path.write_text('{}\nnot json\n')
        result = self.run_cli('submit', self.scenario, '--results', path, code=1)
        self.assertEqual({1, 2}, {p['line'] for p in result['problems']})

    def test_batch_conflict_and_state_override_outside_repository(self):
        """I1/D2: checkout binding and SOP_VERIFY_STATE precedence."""
        self.env['SOP_VERIFY_STATE'] = str(self.base / 'override')
        path = self.results_file()
        self.run_cli('submit', self.scenario, '--results', path)
        self.assertTrue((self.batch_path() / 'rounds/1/round.json').exists())
        self.assertEqual({}, self.files(self.state))
        another = self.scenario.with_name('another.yaml')
        another.write_bytes(self.scenario.read_bytes())
        result = self.run_cli('submit', another, '--results', path, code=1)
        self.assertEqual('batch-conflict', result['error_code'])
        self.env['SOP_VERIFY_STATE'] = str(self.repo / 'state')
        result = self.run_cli('submit', self.scenario, '--results', path, code=1)
        self.assertEqual('source-stale', result['error_code'])
        self.assertFalse((self.repo / 'state').exists())

    def test_submit_rejects_source_or_scenario_change_during_read(self):
        """I1 source-stale: real concurrent edits while a FIFO result is read."""
        path = self.results_file()
        payload = path.read_bytes()
        for target in (self.repo / 'app.txt', self.scenario):
            with self.subTest(target=target.name):
                fifo = path.parent / 'stream'
                os.mkfifo(fifo)
                proc = subprocess.Popen([sys.executable, str(SCRIPT), 'submit', str(self.scenario),
                                         '--results', str(fifo), '--format', 'json'],
                                        cwd=self.repo, env=self.env, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
                descriptor = None
                try:
                    deadline = time.monotonic() + 10
                    while descriptor is None and time.monotonic() < deadline:
                        try:
                            descriptor = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
                        except OSError:
                            if proc.poll() is not None:
                                self.fail(str(proc.communicate()))
                            time.sleep(.01)
                    self.assertIsNotNone(descriptor, 'submit never opened results')
                    target.write_bytes(target.read_bytes() + b' ')
                    expected = self.files(self.repo)
                    os.write(descriptor, payload)
                    os.close(descriptor)
                    descriptor = None
                    stdout, stderr = proc.communicate(timeout=10)
                    self.assertEqual(1, proc.returncode, stdout + stderr)
                    self.assertEqual('source-stale', json.loads(stdout)['error_code'])
                    self.assertEqual(expected, self.files(self.repo))
                    self.assertEqual({}, self.files(self.state))
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
                    if proc.poll() is None:
                        proc.kill()
                        proc.communicate()
                    fifo.unlink()

    def test_import_cases_union_and_preserved_yaml_fields(self):
        """D1/D2; SOP-04-P01: retain original fields; latest complete item wins."""
        first = self.base / 'cases.yaml'
        first.write_text("""metadata: {owner: 测试同事}
# 中文注释
test_cases:
- id: TC1
  title: '测试 ''引号''
    折行'
  priority: P0
  steps: ['打开,页面', 中文]
  expected_results: [成功]
  tags: ["中文", 'a,b']
  custom: {count: 2, rate: 1.5, enabled: true, nothing: null}
- id: TC2
  title: 第二条
- id: TC3
  title: 第三条
""", encoding='utf-8')
        result = self.run_cli('import-cases', self.scenario, first)
        self.assertEqual((3, 0, 0, 3), tuple(result[k] for k in ('added', 'updated', 'unchanged', 'total')))
        union = json.loads((self.batch_path() / 'cases/union.json').read_text())['test_cases']
        self.assertEqual(dict(id='TC1', title="测试 '引号' 折行", priority='P0',
                              steps=['打开,页面', '中文'], expected_results=['成功'], tags=['中文', 'a,b'],
                              custom=dict(count=2, rate=1.5, enabled=True, nothing=None)), union[0])
        second = self.write_json(self.base / 'cases.json',
                                 {'cases': [dict(id='TC3', title='更新'), dict(id='TC4', title='第四条')]})
        result = self.run_cli('import-cases', self.scenario, second)
        self.assertEqual((1, 1, 0, 4), tuple(result[k] for k in ('added', 'updated', 'unchanged', 'total')))
        result = self.run_cli('import-cases', self.scenario, second)
        self.assertEqual((0, 0, 2, 4), tuple(result[k] for k in ('added', 'updated', 'unchanged', 'total')))
        union = json.loads((self.batch_path() / 'cases/union.json').read_text())['test_cases']
        self.assertEqual(dict(id='TC3', title='更新'), next(c for c in union if c['id'] == 'TC3'))
        snapshots = list((self.batch_path() / 'cases/imports').glob('*.json'))
        self.assertEqual(3, len(snapshots))
        self.assertEqual(first.read_text(), json.loads(snapshots[0].read_text())['source'])

    def test_cases_invalid(self):
        """I1/D1: cases-invalid for duplicate, missing fields and wrong shape."""
        for value in ({'cases': [dict(id='TC1', title='one'), dict(id='TC1', title='two')]},
                      {'test_cases': [dict(id='TC1')]}, {'cases': 'wrong'},
                      {'cases': [dict(id='', title='one')]}, {'cases': [5]}):
            with self.subTest(value=value):
                path = self.write_json(self.base / 'invalid.json', value)
                result = self.run_cli('import-cases', self.scenario, path, code=1)
                self.assertEqual('cases-invalid', result['error_code'])
        path.write_text('cases: &cases []')
        result = self.run_cli('import-cases', self.scenario, path, code=1)
        self.assertEqual('cases-invalid', result['error_code'])
        self.assertEqual(1, result['problems'][0]['line'])

    def import_four(self):
        path = self.write_json(self.base / 'cases.json',
                               {'cases': [dict(id=f'TC{i}', title=f'用例{i}') for i in range(1, 5)]})
        self.run_cli('import-cases', self.scenario, path)
        return dict(covered=[dict(case=f'TC{i}', scenarios=['N1-P'], note='依据 SOP') for i in range(1, 4)],
                    conflict=[], disposed=[dict(case='TC4', state='out-of-scope',
                                               reason='范围之外', confirmed_by='负责人')])

    def test_coverage_complete_snapshot(self):
        """D1/D2; SOP-04-P02: each imported case belongs to exactly one class."""
        pairs = self.import_four()
        path = self.write_json(self.base / 'pairs.json', pairs)
        result = self.run_cli('coverage', self.scenario, '--pairs', path)
        self.assertTrue(result['complete'])
        self.assertEqual(4, result['total'])
        snapshots = list((self.batch_path() / 'coverage').glob('*.json'))
        self.assertEqual(1, len(snapshots))
        record = json.loads(snapshots[0].read_text())
        self.assertEqual(pairs, record['pairs'])
        self.assertTrue(record['conclusion']['complete'])

    def test_coverage_missing_duplicate_conflict_and_unknown_scenario(self):
        """D1/I1; SOP-04-N01/N02: separate, named coverage problems saved."""
        pairs = self.import_four()
        pairs['disposed'] = []
        pairs['conflict'] = [pairs['covered'][0]]
        pairs['covered'][1]['scenarios'] = ['SOP-99-P01']
        path = self.write_json(self.base / 'pairs.json', pairs)
        result = self.run_cli('coverage', self.scenario, '--pairs', path, code=1, writes_on_error=True)
        self.assertEqual('scenario-coverage-incomplete', result['error_code'])
        self.assertEqual(['TC4'], result['missing'])
        self.assertEqual(['TC1'], result['duplicate'])
        self.assertEqual(['TC1'], result['conflict'])
        self.assertIn('SOP-99-P01', str(result['problems']))
        self.assertIn('TC2', str(result['problems']))
        records = list((self.batch_path() / 'coverage').glob('*.json'))
        self.assertFalse(json.loads(records[0].read_text())['conclusion']['complete'])
        for change in (dict(disposed=[dict(case='TC4', state='unknown', reason='', confirmed_by='')]),
                       dict(covered=[dict(case='TC5', scenarios=['N1-P'], note='')]),
                       dict(covered='wrong')):
            with self.subTest(change=change):
                bad = dict(pairs, **change)
                self.write_json(path, bad)
                result = self.run_cli('coverage', self.scenario, '--pairs', path, code=1, writes_on_error=True)
                self.assertEqual('scenario-coverage-incomplete', result['error_code'])

    def test_report_without_rounds(self):
        """D2; SOP-05-N01: null rate, explicitly no execution records."""
        result = self.run_cli('report', self.scenario, readonly=True)
        self.assertTrue(result['ok'])
        self.assertEqual(dict(numerator=0, denominator=0, rate=None), result['first_pass_rate'])
        self.assertEqual([], result['rounds'])
        output = self.run_cli('report', self.scenario, fmt=None, readonly=True)
        self.assertIn('尚无执行记录', output)
        self.assertIn('无数据', output)
        self.assertNotIn('0%', output)

    def test_report_seven_sections_rates_latest_results_and_regression(self):
        """D2; SOP-05-P01: same numbers and facts in JSON and Markdown."""
        self.doc['sops'][0]['scenarios'][0]['regression'] = dict(manual='核对终端提示', owner='负责人', trigger='发布前')
        self.save()
        self.scenario.write_text('# 待确认 Q1：退款上限待业务确认\n' + self.scenario.read_text())
        path = self.results_file(dict(zip(('N1-P', 'N1-N', 'N2-P', 'N2-N'), ('pass', 'fail', 'pass', 'pass'))))
        self.run_cli('submit', self.scenario, '--results', path, '--implementer', 'Zhang San')
        path = self.results_file({'N1-N': 'pass'}, executor='Zhang  San')
        self.run_cli('submit', self.scenario, '--results', path, '--implementer', 'zhang san')
        result = self.run_cli('report', self.scenario, readonly=True)
        self.assertEqual(dict(numerator=3, denominator=4, rate=.75), result['first_pass_rate'])
        self.assertEqual([dict(numerator=3, denominator=4, rate=.75), dict(numerator=1, denominator=1, rate=1)],
                         [r['statistics']['pass_rate'] for r in result['rounds']])
        self.assertEqual(dict(check=0, manual=1, pending=3), result['regression']['counts'])
        self.assertEqual('Q1', result['unconfirmed'][0]['id'])
        self.assertEqual('负责人', result['header']['sources'][0]['confirmed_by'])
        self.assertEqual('demo', result['header']['batch'])
        self.assertEqual('演示需求', result['header']['requirement'])
        latest = next(s for s in result['scenarios'] if s['id'] == 'N1-N')
        self.assertEqual('self-check', latest['latest_result']['independence'])
        self.assertEqual('Zhang  San', latest['latest_result']['executor'])
        self.assertEqual('pass', latest['current_status'])
        output = self.run_cli('report', self.scenario, fmt='markdown', readonly=True)
        for section in ('头部', '场景表', '轮次表', '一次通过率', '回归声明', '待确认预期', '未验证范围'):
            self.assertIn('## ' + section, output)
        for ratio in ('3/4', '1/1'):
            self.assertIn(ratio, output)
        for label, count in result['regression']['counts'].items():
            self.assertIn(f'{label}: {count}', output)
        for value in ('Q1', 'self-check', 'Zhang  San', '核对结果', result['header']['product_fingerprint']):
            self.assertIn(value, output)
        evidence = latest['latest_result']['evidence'][0]
        self.assertIn(evidence['sha256'][:12], output)
        self.assertIn(Path(evidence['path']).name, output)

    def test_report_first_current_fingerprint_and_unverified_scope(self):
        """D2: first blocked/skip excluded; report current-content history."""
        self.doc['sops'][0]['scenarios'][0]['regression'] = dict(check='unit', cases=['Demo::test_a'])
        self.doc['sops'][0]['scenarios'][1]['regression'] = dict(pending='Q-AUTO')
        self.save()
        path = self.results_file({'N1-P': 'blocked', 'N1-N': 'skip', 'N2-P': 'pass', 'N2-N': 'fail'})
        self.run_cli('submit', self.scenario, '--results', path)
        self.run_cli('submit', self.scenario, '--results', self.results_file({'N2-N': 'pass'}))
        result = self.run_cli('report', self.scenario, readonly=True)
        self.assertEqual(dict(numerator=1, denominator=2, rate=.5), result['first_pass_rate'])
        self.assertEqual({'N1-P', 'N1-N'}, {s['scenario'] for s in result['unverified']})
        self.assertTrue(all(s['finding'] == 'Q1' for s in result['unverified']))
        self.assertEqual(dict(check=1, manual=0, pending=3), result['regression']['counts'])
        self.doc['sops'][1]['scenarios'][1]['expected'] = ['新预期']
        self.save()
        result = self.run_cli('report', self.scenario, readonly=True)
        self.assertEqual(dict(numerator=1, denominator=1, rate=1), result['first_pass_rate'])
        self.assertEqual('changed', next(s for s in result['scenarios'] if s['id'] == 'N2-N')['current_status'])

    def test_yaml_plain_punctuation_multiline_flow_and_escapes(self):
        """D1: punctuation inside plain scalars and multiline flow collections."""
        path = self.base / 'cases.yaml'
        path.write_text("""cases:
- id: TC
  title: text, [brackets] and 'quotes'
  steps:
  - ordinary, text
  - 'single

    paragraph'
  - "double

    paragraph"
  tags: ["中文",
    # 中间注释
    'it''s', "a,b"]
  values: [1, -2, 3.5, 1.0e+3, true, false, null]
  escaped: "a\\n\\t\\u4e2d"
""", encoding='utf-8')
        self.run_cli('import-cases', self.scenario, path)
        item = json.loads((self.batch_path() / 'cases/union.json').read_text())['test_cases'][0]
        self.assertEqual("text, [brackets] and 'quotes'", item['title'])
        self.assertEqual(['ordinary, text', 'single\nparagraph', 'double\nparagraph'], item['steps'])
        self.assertEqual(['中文', "it's", 'a,b'], item['tags'])
        self.assertEqual([1, -2, 3.5, 1000., True, False, None], item['values'])
        self.assertEqual('a\n\t中', item['escaped'])

    def test_invalid_types_and_missing_scenario_are_structured_errors(self):
        """I1/D1: malformed field types never escape as Python exceptions."""
        result = self.run_cli('check', 'missing.yaml', code=1)
        self.assertEqual('scenario-file-invalid', result['error_code'])
        for field, value in (('negative_type', []), ('regression', []), ('verify', {}),
                             ('id', ['bad']), ('expected', 'wrong'), ('polarity', {})):
            with self.subTest(field=field):
                self.doc = example()
                self.doc['sops'][0]['scenarios'][1][field] = value
                self.save()
                result = self.run_cli('check', self.scenario, code=1)
                self.assertEqual('scenario-file-invalid', result['error_code'])

    def test_text_rates_and_all_help_commands(self):
        """I1/D2: discoverable command surface and text numerator/denominator."""
        commands = ('check', 'pending', 'submit', 'import-cases', 'coverage', 'report')
        output = self.run_cli('--help', fmt=None, readonly=True)
        for command in commands:
            self.assertIn(command, output)
            self.assertIn('usage:', self.run_cli(command, '--help', fmt=None, readonly=True))
        path = self.results_file({'N1-P': 'pass', 'N1-N': 'fail', 'N2-P': 'pass', 'N2-N': 'pass'})
        output = self.run_cli('submit', self.scenario, '--results', path, fmt='text')
        self.assertIn('3/4', output)
        self.assertIn('failed', self.run_cli('pending', self.scenario, fmt='text', readonly=True))

    def test_product_fingerprint_files_deletions_and_exclusions(self):
        """D2: fingerprint paths/content, deleted tracked, ignored/untracked files."""
        # The oracle enumerates fixture files directly, independently of git ls-files.
        self.scenario = self.repo / 'workflow.yaml'
        self.save()
        entries = self.repo / 'external-entries.json'
        self.write_json(entries, {'entries': {'cli': self.entry}})
        # All commands besides check discover the sibling entries.yaml.
        self.entries = self.repo / 'entries.yaml'
        self.write_json(self.entries, {'entries': {'cli': self.entry}})
        (self.repo / '.gitignore').write_text('ignored.txt\n')
        (self.repo / 'ignored.txt').write_text('ignore')
        (self.repo / 'new.txt').write_text('untracked')
        path = self.results_file()
        self.run_cli('submit', self.scenario, '--results', path)
        record = json.loads((self.batch_path() / 'rounds/1/round.json').read_text())
        selected = ('.gitignore', 'app.txt', 'external-entries.json', 'new.txt')
        files = [dict(path=name, sha256=hashlib.sha256((self.repo / name).read_bytes()).hexdigest()) for name in selected]
        expected = hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False,
                                             separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(expected, record['product_fingerprint'])
        (self.repo / 'ignored.txt').write_text('changed ignored')
        self.entries.write_text('# comment\n' + self.entries.read_text())
        self.assertEqual([], self.run_cli('pending', self.scenario, readonly=True)['pending'])
        (self.repo / 'app.txt').unlink()
        self.run_cli('submit', self.scenario, '--results', path)
        record = json.loads((self.batch_path() / 'rounds/2/round.json').read_text())
        files[1] = dict(path='app.txt', deleted=True)
        expected = hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False,
                                             separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(expected, record['product_fingerprint'])

    def test_yaml_nested_block_arrays_and_numeric_scalars(self):
        """D1: nested block/flow collections emitted by default PyYAML."""
        path = self.base / 'nested.yaml'
        path.write_text("""cases:
- id: TC
  title: nested
  matrix:
  - - 1
    - 2
  - - 3
    - 4
  objects:
  - - name: first
      flags: [true, false]
    - name: second
  number: 1.2e-3
""")
        self.run_cli('import-cases', self.scenario, path)
        item = json.loads((self.batch_path() / 'cases/union.json').read_text())['test_cases'][0]
        self.assertEqual([[1, 2], [3, 4]], item['matrix'])
        self.assertEqual([[dict(name='first', flags=[True, False]), dict(name='second')]], item['objects'])
        self.assertEqual(.0012, item['number'])

    def test_no_repository_writes_through_state_symlinks(self):
        """D2: even a state child pointing into the repo cannot receive writes."""
        batch = self.batch_path()
        batch.mkdir(parents=True)
        (batch / 'rounds').symlink_to(self.repo, target_is_directory=True)
        result = self.run_cli('submit', self.scenario, '--results', self.results_file(), code=1)
        self.assertEqual('source-stale', result['error_code'])
        self.assertFalse((batch / 'batch.json').exists())

    def test_git_index_unchanged_when_file_stat_needs_refresh(self):
        """D2: read-only Git calls must not refresh the repository index."""
        self.env.pop('GIT_OPTIONAL_LOCKS', None)
        app = self.repo / 'app.txt'
        stat = app.stat()
        os.utime(app, ns=(stat.st_atime_ns, stat.st_mtime_ns - 10_000_000_000))
        self.run_cli('pending', self.scenario, readonly=True)

    def test_unconfirmed_only_actual_yaml_comment_lines(self):
        """D1/D2: a comment-looking line inside a quoted scalar is content."""
        content = self.yaml_fixture().replace("title: '中文 ''引号''\n      折行'",
            "title: '中文\n      # 待确认 FALSE：属于标题内容\n      折行'")
        self.scenario.write_text('# 待确认 TRUE：真实待确认预期\n' + content)
        result = self.run_cli('report', self.scenario, readonly=True)
        self.assertEqual(['TRUE'], [item['id'] for item in result['unconfirmed']])


if __name__ == '__main__':
    unittest.main()
