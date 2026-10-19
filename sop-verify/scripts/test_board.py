"""SOP-VERIFY-2 revision 2: public CLI and HTTP contracts (I1–I4, D1)."""
from __future__ import annotations

import json
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import secrets
import subprocess
import sys
import threading
import unittest

import test_sop as fixtures


class CliFixture:
    setUp = fixtures.SopTests.setUp
    write_json = fixtures.SopTests.write_json
    save = fixtures.SopTests.save
    files = fixtures.SopTests.files
    run_cli = fixtures.SopTests.run_cli
    results_file = fixtures.SopTests.results_file

    def declare_check(self):
        self.write_json(self.entries, dict(entries={'cli': self.entry}, checks={
            'unit': dict(argv=['python3', '-m', 'unittest'], timeout=60,
                         format='junit', report='{output}/results.xml', required_env=[])}))


class EntryTests(CliFixture, unittest.TestCase):
    def test_invalid_entry_and_check_objects_locate_declaration_lines(self):
        """D1: invalid whole declarations still identify the original YAML/JSON line."""
        for source in ('entries', 'tw'):
            for area in ('entries', 'checks'):
                with self.subTest(source=source, area=area):
                    document = dict(entries={'cli': self.entry}, checks={
                        'unit': dict(argv=['python3'], timeout=1, format='go-json')})
                    document[area]['cli' if area == 'entries' else 'unit'] = False
                    if source == 'tw':
                        document['acceptance_entries'] = document.pop('entries')
                        self.entries.unlink(missing_ok=True)
                        target = self.repo / '.tw/config.json'
                    else:
                        target = self.entries
                    self.write_json(target, document)
                    raw = json.dumps(document, ensure_ascii=False, indent=2)
                    target.write_text(raw)
                    line = next(i for i, value in enumerate(raw.splitlines(), 1) if ': false' in value)
                    result = self.run_cli('check', self.scenario, code=1)
                    self.assertEqual('entries-invalid', result['error_code'])
                    self.assertEqual(line, result['problems'][0]['line'])
    def test_candidate_commands_checks_and_tw_source(self):
        """D1: new entry fields, declared checks, and the .tw source work."""
        self.entry.update(candidate='start', address_env='APP_URL', start=['python3', 'app.py'], reload=['kill', '-HUP'])
        self.doc['sops'][0]['scenarios'][0]['regression'] = dict(check='unit', cases=['test_demo'])
        self.save()
        self.declare_check()
        self.run_cli('check', self.scenario, readonly=True)
        document = json.loads(self.entries.read_text())
        self.entries.unlink()
        document['checks']['unit']['purpose'] = 'Only the supported check fields are selected'
        self.write_json(self.repo / '.tw/config.json', dict(
            acceptance_entries=document['entries'], checks=document['checks']))
        self.run_cli('check', self.scenario, readonly=True)

    def test_entries_invalid_fields_and_exact_lines(self):
        """D1: invalid entry/check values and unknown YAML fields name their lines."""
        valid = dict(argv=['python3', '-m', 'unittest'], timeout=30, format='go-json')
        for field, value in [('candidate', 'remote'), ('candidate', []), ('start', []),
                             ('reload', ['']), ('start', 'python3'), ('extra', True)]:
            with self.subTest(entry=field, value=value):
                document = dict(entries={'cli': dict(self.entry, **{field: value})})
                raw = json.dumps(document, ensure_ascii=False, indent=2)
                self.entries.write_text(raw)
                result = self.run_cli('check', self.scenario, code=1, readonly=True)
                self.assertEqual('entries-invalid', result['error_code'])
                expected_line = next(i for i, line in enumerate(raw.splitlines(), 1)
                                     if f'"{field}"' in line)
                self.assertTrue(any(p['line'] == expected_line and field in p['problem']
                                    for p in result['problems']))
        for field, value in [('argv', []), ('argv', ['']), ('cwd', 1), ('timeout', True),
                             ('timeout', 0), ('timeout', 1.5), ('format', 'json'),
                             ('required_env', 'NAME'), ('required_env', ['']), ('extra', True)]:
            with self.subTest(check=field, value=value):
                document = dict(entries={'cli': self.entry}, checks={'unit': dict(valid, **{field: value})})
                raw = json.dumps(document, ensure_ascii=False, indent=2)
                self.entries.write_text(raw)
                result = self.run_cli('check', self.scenario, code=1, readonly=True)
                self.assertEqual('entries-invalid', result['error_code'])
                expected_line = next(i for i, line in enumerate(raw.splitlines(), 1)
                                     if f'"{field}"' in line)
                self.assertTrue(any(p['line'] == expected_line and field in p['problem']
                                    for p in result['problems']))
        for entry, check, phrase in [
            (dict(self.entry, candidate='start'), valid, 'start'),
            (self.entry, dict(valid, format='junit'), 'report'),
        ]:
            self.write_json(self.entries, dict(entries={'cli': entry}, checks={'unit': check}))
            result = self.run_cli('check', self.scenario, code=1)
            self.assertIn(phrase, str(result['problems']))

    def test_undeclared_regression_check_in_check_pending_submit(self):
        """D1: all three commands reject undeclared checks at the reference line."""
        self.doc['sops'][0]['scenarios'][0]['regression'] = dict(check='missing', cases=['test_demo'])
        raw = json.dumps(self.doc, ensure_ascii=False, indent=2)
        self.scenario.write_text(raw)
        line = next(i for i, value in enumerate(raw.splitlines(), 1) if '"check":' in value)
        path = self.results_file()
        for args in [('check',), ('pending',), ('submit', '--results', str(path))]:
            command, *options = args
            result = self.run_cli(command, self.scenario, *options, code=1, readonly=True)
            self.assertEqual('scenario-file-invalid', result['error_code'])
            self.assertEqual([dict(line=line, problem='N1-P regression.check 引用未声明检查 missing')],
                             result['problems'])

    def test_tw_invalid_check_preserves_source_line(self):
        """D1: projected tw checks retain real JSON line numbers."""
        self.entries.unlink()
        raw = json.dumps(dict(acceptance_entries={'cli': self.entry}, checks={
            'unit': dict(argv=['python3'], timeout=0, format='go-json', purpose='ignored')}),
            ensure_ascii=False, indent=2)
        self.write_json(self.repo / '.tw/config.json', {})
        (self.repo / '.tw/config.json').write_text(raw)
        result = self.run_cli('check', self.scenario, code=1)
        self.assertEqual('entries-invalid', result['error_code'])
        self.assertEqual(next(i for i, line in enumerate(raw.splitlines(), 1) if '"timeout"' in line),
                         result['problems'][0]['line'])

    def test_start_requires_address_and_tw_check_metadata_is_accepted(self):
        """D1 revision 2: start requires address_env; check metadata is preserved and compared."""
        self.entry.update(candidate='start', start=['python3', 'app.py'])
        self.declare_check()
        result = self.run_cli('check', self.scenario, code=1)
        self.assertEqual('entries-invalid', result['error_code'])
        self.assertIn('address_env', str(result['problems']))
        self.entry['address_env'] = 'APP_URL'
        self.declare_check()
        document = json.loads(self.entries.read_text())
        document['checks']['unit'].update(purpose='可读说明', required_cases=['test_demo'],
                                         environment={'kind': 'stateless'}, coverage={'level': 'journey'})
        self.write_json(self.entries, document)
        self.run_cli('check', self.scenario)
        other = dict(document['checks']['unit'], timeout=99)
        self.write_json(self.repo / '.tw/config.json', dict(acceptance_entries={'cli': self.entry}, checks={'unit': other}))
        result = self.run_cli('check', self.scenario)
        self.assertIn('unit 检查', str(result['warnings']))
        # Sibling checks take precedence; an undeclared check cannot be borrowed from tw.
        self.doc['sops'][0]['scenarios'][0]['regression'] = dict(check='only-tw', cases=['test_demo'])
        self.save()
        self.write_json(self.repo / '.tw/config.json', dict(acceptance_entries={'cli': self.entry}, checks={'only-tw': other}))
        result = self.run_cli('check', self.scenario, code=1)
        self.assertEqual('scenario-file-invalid', result['error_code'])


class BoardFixture(CliFixture):
    def setUp(self):
        super().setUp()
        self.requests = []
        self.routes = {}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        self.env['SOP_BOARD_TOKEN'] = secrets.token_hex(24)  # Generated fixture, never persisted.
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def handle_request(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                headers = {k.lower(): v for k, v in self.headers.items() if k.lower() != 'authorization'}
                headers['authorization_present'] = 'Authorization' in self.headers
                headers['authorization_valid'] = (
                    self.headers.get('Authorization') == 'Bearer ' + owner.env.get('SOP_BOARD_TOKEN', ''))
                request = dict(method=self.command, path=self.path, headers=headers, body=body)
                owner.requests.append(request)
                response = owner.routes.get((self.command, self.path))
                if callable(response):
                    response = response(request)
                if response is None:
                    response = (200, dict(ok=True, scenarios=[]))
                status, value = response
                payload = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json' if not isinstance(value, bytes) else 'text/plain')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            do_GET = do_PUT = do_POST = handle_request

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_board)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.env['SOP_BOARD_URL'] = self.url + '///'
        self.key = 'github-com-demo-org-demo-app'
        self.api = '/api/v1/projects/' + self.key + '/batches/demo'
        subprocess.run(['git', '-C', str(self.repo), 'remote', 'add', 'origin',
                        'https://github.com/demo-org/demo-app.git'], check=True, env=self.env)

    def close_board(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def cli(self, *args, code=0, fmt='json', writes=False, timeout=45):
        before, state = self.files(self.repo), self.files(self.state)
        command = [sys.executable, str(fixtures.SCRIPT), *map(str, args)]
        if fmt:
            command += ['--format', fmt]
        process = subprocess.run(command, cwd=self.repo, env=self.env,
                                 capture_output=True, text=True, timeout=timeout)
        token = self.env.get('SOP_BOARD_TOKEN', '')
        # Do not let a failing assertion print a generated authentication value.
        output = (process.stdout + process.stderr).replace(token, '***') if token else process.stdout + process.stderr
        self.assertTrue(not token or token not in process.stdout + process.stderr, '令牌出现在命令输出')
        self.assertEqual(code, process.returncode, output)
        if not writes:
            self.assertEqual(before, self.files(self.repo), '命令修改了仓库文件')
        after = self.files(self.state)
        if args[0] == 'submit' and code == 0:
            marker = str((fixtures.SopTests.batch_path(self) / 'batch.json').relative_to(self.state))
            self.assertLessEqual(set(after) - set(state), {marker}, '看板命令写入了轮次或证据')
            self.assertEqual(state, {name: value for name, value in after.items() if name in state})
            self.assertEqual({'scenario_file': 'docs/sop/demo.yaml'}, json.loads(after[marker]))
        else:
            self.assertEqual(state, after, '看板命令写入了本机状态目录')
        if code == 2:
            self.assertEqual('', process.stdout)
            self.assertIn('usage:', process.stderr)
            return ''
        self.assertEqual('', process.stderr, output)
        return json.loads(process.stdout) if fmt == 'json' else process.stdout

    def prepare_submit(self):
        statistics = dict(executed=4, **{'pass': 4, 'fail': 0, 'blocked': 0, 'skip': 0},
                          pass_rate=dict(numerator=4, denominator=4, rate=1))
        self.routes['PUT', self.api + '/scenario-file'] = (200, dict(ok=True, version=1))
        self.routes['POST', '/api/v1/evidence'] = lambda request: (
            200, dict(ok=True, sha256=hashlib.sha256(request['body']).hexdigest(), size=len(request['body'])))
        self.routes['POST', self.api + '/rounds'] = (200, dict(ok=True, round=7, statistics=statistics, queues={}))
        return statistics

    def prepare_merge(self, base=None, merged=None):
        self.task_query = '/api/v1/tasks?project=' + self.key + '&batch=demo'
        self.merge_api = self.api + '/merges/19'
        self.base_bytes = self.scenario.read_bytes() if base is None else base
        self.routes['GET', self.task_query] = (200, dict(ok=True, tasks=[
            dict(id=19, kind='merge', status='已完成', scenario_file_sha256=(
                hashlib.sha256(self.base_bytes).hexdigest() if self.base_bytes else '')),
            dict(id=30, kind='merge', status='失败'), dict(id=7, kind='merge', status='已完成'),
            dict(id=99, kind='execute', status='已完成')]))
        if merged is None:
            document = json.loads(self.scenario.read_text())
            document['metadata']['version'] = 2
            merged = json.dumps(document, ensure_ascii=False, indent=2).encode() + b'\n'
        self.merged_bytes = merged
        self.pairs = dict(covered=[dict(case='C1', scenarios=['N1-P'], note='按用例合并')], conflict=[], disposed=[])
        self.routes['GET', self.merge_api + '/scenario-file'] = (200, self.merged_bytes)
        self.routes['GET', self.merge_api + '/pairs.json'] = (200, self.pairs)


class BoardTests(BoardFixture, unittest.TestCase):
    def test_pending_regression_status_passed_failed_pending_and_missing(self):
        """I3 revision 2 / SOP-BOARD-4 I5: regression status controls guarded and failed."""
        scenarios = [s for node in self.doc['sops'] for s in node['scenarios']]
        for scenario in scenarios:
            scenario['regression'] = dict(check='unit', cases=['test_demo'])
        self.declare_check()
        self.save()
        rows = [dict(scenario=s['id'], fingerprint=fixtures.fingerprint(s), queue='retest',
                     latest_agent=dict(status='pass', round=1), latest_manual=None)
                for s in scenarios]
        for row, status in zip(rows, ('passed', 'failed', 'pending')):
            row['regression_status'] = status
        self.routes['GET', self.api + '/scenarios'] = (200, dict(ok=True, scenarios=rows))
        result = self.cli('pending', self.scenario)
        self.assertEqual([dict(scenario='N1-N', reason='failed')], result['pending'])
        self.assertEqual([dict(scenario=ident, check='unit', message=message) for ident, message in (
            ('N1-P', '检查通过'), ('N2-P', '检查待运行'), ('N2-N', '检查待运行'))], result['guarded'])
        # A regression check can have run before any browser/Agent result exists.
        rows[0]['latest_agent'] = None
        result = self.cli('pending', self.scenario)
        self.assertEqual('检查通过', result['guarded'][0]['message'])

    def test_import_cases_pushes_and_keeps_local_coverage_snapshot(self):
        """I2 revision 2: board uploads and local snapshots both receive the original cases."""
        document = dict(metadata=dict(module='示例', feature='验收', owner='测试负责人', last_reviewed='2026-10-20'),
                        test_cases=[dict(id='TC_DEMO_001', title='测试用例', priority='P0', type='functional',
                                        steps=['运行'], expected_results=['结果正确'], tags=['section:演示'])])
        cases = self.write_json(self.base / '用例.json', document)
        self.routes['POST', self.api + '/cases'] = (200, dict(ok=True, upload=3, added=1, updated=0,
                                                            unchanged=0, union_count=1))
        result = self.run_cli('import-cases', self.scenario, cases)
        self.assertEqual(3, result['upload'])
        self.assertEqual(1, result['union_count'])
        request = self.requests[-1]
        self.assertEqual('POST', request['method'])
        self.assertTrue(request['headers']['authorization_valid'])
        self.assertEqual(dict(filename='用例.json', content=cases.read_text(), uploaded_by='sop-verify'),
                         json.loads(request['body']))
        union = json.loads((fixtures.SopTests.batch_path(self) / 'cases/union.json').read_text())
        self.assertEqual(document['test_cases'], union['test_cases'])
        pairs = self.write_json(self.base / 'pairs.json', dict(covered=[dict(case='TC_DEMO_001', scenarios=['N1-P'], note='一致')],
                                                             conflict=[], disposed=[]))
        self.run_cli('coverage', self.scenario, '--pairs', pairs)
        state = self.files(self.state)
        self.routes['POST', self.api + '/cases'] = (422, dict(ok=False, error_code='cases-invalid',
            problems=[dict(field='test_cases', line=5, problem='不合格')]))
        result = self.run_cli('import-cases', self.scenario, cases, code=1)
        self.assertEqual('board-rejected', result['error_code'])
        self.assertEqual(state, self.files(self.state))
        self.requests.clear()
        self.env.pop('SOP_BOARD_TOKEN')
        result = self.run_cli('import-cases', self.scenario, cases, code=1)
        self.assertEqual('board-token-missing', result['error_code'])
        self.assertEqual([], self.requests)

    def test_board_batch_binding_detects_other_scenario_path(self):
        """I2 revision 2: board rounds retain batch.json and reject reuse by another file."""
        self.prepare_submit()
        self.cli('submit', self.scenario, '--results', self.results_file())
        other = self.scenario.with_name('other.yaml')
        other.write_bytes(self.scenario.read_bytes())
        self.requests.clear()
        result = self.cli('submit', other, '--results', self.results_file(), code=1)
        self.assertEqual('batch-conflict', result['error_code'])
        self.assertEqual([], self.requests)

    def test_pull_missing_file_batch_and_parameter_boundaries(self):
        """I4: missing destinations use --batch; inside-repository pair paths exit 2."""
        self.prepare_merge(base=b'')
        self.scenario.unlink()
        self.cli('pull', self.scenario, code=2)
        self.assertEqual([], self.requests)
        result = self.cli('pull', self.scenario, '--batch', 'demo', writes=True)
        self.assertEqual(19, result['task'])
        self.assertEqual(self.merged_bytes, self.scenario.read_bytes())
        self.cli('check', self.scenario)
        self.requests.clear()
        self.cli('pull', self.scenario, '--batch', 'other', code=2)
        self.assertEqual([], self.requests)
        for output in (self.repo / 'pairs.json', 'docs/../pairs.json'):
            self.requests.clear()
            self.cli('pull', self.scenario, '--pairs', output, code=2)
            self.assertEqual([], self.requests)
        link = self.base / 'linked-repository'
        link.symlink_to(self.repo, target_is_directory=True)
        self.cli('pull', self.scenario, '--pairs', link / 'pairs.json', code=2)
        self.env.pop('SOP_BOARD_URL')
        result = self.cli('pull', self.scenario, code=1)
        self.assertEqual('board-not-configured', result['error_code'])
        self.scenario.unlink()
        self.cli('pull', self.scenario, code=2)
        result = self.cli('pull', self.scenario, '--batch', 'demo', code=1)
        self.assertEqual('board-not-configured', result['error_code'])

    def test_pull_no_completed_merge_and_failed_download_never_write(self):
        """I4/I1: no merge, unfinished merges, board rejection, invalid downloads."""
        self.prepare_merge()
        route = self.routes['GET', self.task_query]
        for tasks in ([], [dict(id=1, kind='merge', status='待同步')],
                      [dict(id=2, kind='execute', status='已完成')]):
            self.routes['GET', self.task_query] = (200, dict(ok=True, tasks=tasks))
            result = self.cli('pull', self.scenario, code=1)
            self.assertEqual('merge-not-found', result['error_code'])
        self.routes['GET', self.task_query] = route
        self.routes['GET', self.merge_api + '/pairs.json'] = (404, dict(ok=False,
            error_code='merge-result-not-found', problems=[dict(field='task', problem='结果不存在')]))
        pairs = self.base / 'pairs.json'
        result = self.cli('pull', self.scenario, '--pairs', pairs, code=1)
        self.assertEqual('board-rejected', result['error_code'])
        self.assertFalse(pairs.exists())
        self.routes['GET', self.merge_api + '/pairs.json'] = (200, self.pairs)
        self.routes['GET', self.merge_api + '/scenario-file'] = (200, b'not a scenario')
        result = self.cli('pull', self.scenario, '--pairs', pairs, code=1)
        self.assertEqual('scenario-file-invalid', result['error_code'])
        self.assertFalse(pairs.exists())

    def test_submit_text_uses_board_statistics_and_pending_after_registration(self):
        """I2/I3: board statistics are preserved and pending is fetched after the round."""
        self.prepare_submit()
        stats = dict(agent_pass_rate=dict(numerator=4, denominator=4, rate=1),
                     manual_pass_rate=dict(numerator=0, denominator=0, rate=None))
        def register(request):
            self.routes['GET', self.api + '/scenarios'] = (200, dict(ok=True, scenarios=[dict(
                scenario=s['id'], fingerprint=fixtures.fingerprint(s), status='pass', queue='retest',
                latest_agent=dict(status='pass', number=8), latest_manual=None)
                for n in self.doc['sops'] for s in n['scenarios']]))
            return 200, dict(ok=True, round=8, statistics=stats, queues={})
        self.routes['POST', self.api + '/rounds'] = register
        path = self.results_file()
        output = self.cli('submit', self.scenario, '--results', path, fmt='text')
        for phrase in ('第 8 轮', '4/4', '待执行：无', self.url + '/p/'):
            self.assertIn(phrase, output)
        self.assertTrue(any(r['path'] == self.api + '/scenarios' for r in self.requests[
            next(i for i, r in enumerate(self.requests) if r['path'].endswith('/rounds')) + 1:] ))
        result = self.cli('submit', self.scenario, '--results', path)
        self.assertEqual(stats, result['statistics'])
        self.assertEqual([], result['pending'])

    def test_board_timeout_is_thirty_seconds(self):
        """I1: an actual stalled HTTP response times out after 30 seconds."""
        import time
        release = threading.Event()
        self.addCleanup(release.set)
        def stall(request):
            release.wait(35)
            return 200, dict(ok=True, scenarios=[])
        self.routes['GET', self.api + '/scenarios'] = stall
        start = time.monotonic()
        result = self.cli('pending', self.scenario, code=1)
        elapsed = time.monotonic() - start
        self.assertEqual('board-unavailable', result['error_code'])
        self.assertIn(self.url, str(result['problems']))
        self.assertIn('timed out', str(result['problems']))
        self.assertGreaterEqual(elapsed, 29)
        self.assertLess(elapsed, 34)

    def test_pull_conflict_never_writes(self):
        """I4: local content diverging from both merge basis and result must be pushed first."""
        self.prepare_merge()
        self.scenario.write_bytes(self.scenario.read_bytes() + b' ')
        pairs = self.base / 'pairs.json'
        pairs.write_text('preserve this file')
        result = self.cli('pull', self.scenario, '--pairs', pairs, code=1)
        self.assertEqual('pull-conflict', result['error_code'])
        self.assertIn('submit', str(result['problems']))
        self.assertIn('重新合并', str(result['problems']))
        self.assertEqual('preserve this file', pairs.read_text())

    def test_pull_latest_merge_and_pairs_then_check(self):
        """I4: latest completed merge wins, pairs are external, and repeated pulls do not rewrite."""
        self.prepare_merge()
        output = self.base / 'download/pairs.json'
        result = self.cli('pull', self.scenario, '--pairs', output, writes=True)
        self.assertEqual(19, result['task'])
        self.assertEqual(1, result['pairs_count'])
        self.assertEqual([str(self.scenario), str(output)], result['written'])
        self.assertEqual(self.merged_bytes, self.scenario.read_bytes())
        self.assertEqual(self.pairs, json.loads(output.read_text()))
        self.assertEqual(self.task_query, self.requests[0]['path'])
        self.cli('check', self.scenario)
        before = self.scenario.stat().st_mtime_ns
        result = self.cli('pull', self.scenario)
        self.assertEqual([], result['written'])
        self.assertEqual(1, result['pairs_count'])
        self.assertEqual(before, self.scenario.stat().st_mtime_ns)
        text = self.cli('pull', self.scenario, fmt='text')
        self.assertIn('19', text)
        self.assertIn('1', text)

    def test_submit_token_validation_incomplete_and_stage_rejections(self):
        """I1/I2: reject local invalid results and stop on errors at each write stage."""
        self.prepare_submit()
        path = self.results_file()
        token = self.env.pop('SOP_BOARD_TOKEN')
        result = self.cli('submit', self.scenario, '--results', path, code=1)
        self.assertEqual('board-token-missing', result['error_code'])
        self.assertEqual([], self.requests)
        self.env['SOP_BOARD_TOKEN'] = token
        short = self.results_file({'N1-P': 'pass'})
        result = self.cli('submit', self.scenario, '--results', short, code=1)
        self.assertEqual('scenario-results-incomplete', result['error_code'])
        self.assertIn('N2-N', str(result['problems']))
        self.assertTrue(all(request['method'] == 'GET' for request in self.requests))
        path = self.results_file()
        for method, endpoint, status in [('PUT', self.api + '/scenario-file', 401),
                                         ('POST', '/api/v1/evidence', 422),
                                         ('POST', self.api + '/rounds', 409)]:
            with self.subTest(endpoint=endpoint):
                self.prepare_submit()
                self.requests.clear()
                problems = [dict(field='fingerprint', problem='拒绝登记')]
                self.routes[method, endpoint] = (status, dict(ok=False, error_code='server-rejection', problems=problems))
                result = self.cli('submit', self.scenario, '--results', path, code=1)
                self.assertEqual('board-rejected', result['error_code'])
                self.assertIn(dict(line=None, problem='fingerprint：拒绝登记'), result['problems'])
                self.assertIn('server-rejection', str(result['problems']))
                self.assertEqual(endpoint, self.requests[-1]['path'])
        path.write_text('{}\n')
        self.requests.clear()
        result = self.cli('submit', self.scenario, '--results', path, code=1)
        self.assertEqual('scenario-results-invalid', result['error_code'])
        self.assertEqual([], self.requests)

    def test_submit_default_author_tw_entries_and_local_case_snapshots(self):
        """I2/D1: fallback author, projected tw entries/checks, cases still stay local."""
        self.prepare_submit()
        self.declare_check()
        document = json.loads(self.entries.read_text())
        self.entries.unlink()
        document['checks']['unit']['purpose'] = 'Not a field in pushed checks'
        self.entry.update(candidate='checkout', reload=['echo', 'ready'])
        self.write_json(self.repo / '.tw/config.json', dict(acceptance_entries={'cli': self.entry}, checks=document['checks']))
        cases = self.write_json(self.base / 'cases.json', dict(cases=[dict(id='C1', title='测试用例')]))
        self.run_cli('import-cases', self.scenario, cases)
        pairs = self.write_json(self.base / 'pairs.json', dict(covered=[dict(case='C1', scenarios=['N1-P'], note='一致')],
                                                             conflict=[], disposed=[]))
        self.run_cli('coverage', self.scenario, '--pairs', pairs)
        state = self.files(self.state)
        self.cli('submit', self.scenario, '--results', self.results_file())
        self.assertEqual(state, self.files(self.state))
        push = json.loads(next(r['body'] for r in self.requests if r['method'] == 'PUT'))
        self.assertEqual('sop-verify', push['pushed_by'])
        self.assertNotIn('sop_sources', push)
        self.assertEqual({'cli': self.entry}, push['entries']['entries'])
        self.assertEqual('Not a field in pushed checks', push['entries']['checks']['unit']['purpose'])
        round_body = json.loads(next(r['body'] for r in self.requests if r['path'].endswith('/rounds')))
        self.assertEqual('sop-verify', round_body['submitted_by'])
        self.assertNotIn('implementer', round_body)

    def test_submit_source_stale_before_round(self):
        """I2: concurrent source/scenario changes fail; no local round or evidence is written."""
        path = self.results_file()
        for target in (self.repo / 'app.txt', self.scenario):
            for stage in ('/scenario-file', '/api/v1/evidence'):
                with self.subTest(target=target.name, stage=stage):
                    statistics = self.prepare_submit()
                    self.requests.clear()
                    original = target.read_bytes()
                    def edit(request):
                        target.write_bytes(original + b' ')
                        return (200, dict(ok=True, version=1, round=7, statistics=statistics))
                    self.routes['PUT' if stage == '/scenario-file' else 'POST',
                                self.api + stage if stage == '/scenario-file' else stage] = edit
                    result = self.cli('submit', self.scenario, '--results', path, code=1, writes=True)
                    self.assertEqual('source-stale', result['error_code'])
                    self.assertEqual(original + b' ', target.read_bytes())
                    self.assertFalse(any(r['path'].endswith('/rounds') for r in self.requests))
                    target.write_bytes(original)

    def test_token_never_appears_in_error_or_report(self):
        """I1: even a server echo cannot expose the authentication value in CLI output."""
        self.routes['GET', self.api + '/scenarios'] = (401, dict(ok=False, error_code='unauthorized',
            problems=[dict(field='authorization', problem='echo ' + self.env['SOP_BOARD_TOKEN'])]))
        result = self.cli('pending', self.scenario, code=1)
        self.assertIn('***', str(result['problems']))
        self.cli('pending', self.scenario, code=1, fmt='text')
        self.routes['GET', self.api + '/report.md'] = (200, ('# ' + self.env['SOP_BOARD_TOKEN']).encode())
        self.assertEqual('# ***', self.cli('report', self.scenario, fmt='markdown'))

    def test_submit_payload_sources_evidence_dedup_and_idempotency(self):
        """I1/I2: full push, source selection, evidence dedup, round payload and no local writes."""
        from urllib.parse import quote
        statistics = self.prepare_submit()
        subprocess.run(['git', '-C', str(self.repo), 'config', 'user.name', '测试提交人'], check=True, env=self.env)
        source_path = self.repo / 'docs/source.md'
        source_path.write_text('# 已确认的 SOP\n', encoding='utf-8')
        second_path = self.repo / 'docs/second.md'
        second_path.write_text('不会作为首个来源上传\n', encoding='utf-8')
        self.doc['metadata']['sources'] = [
            dict(ref='位置 missing.md docs/source.md#流程 docs/second.md 第 1 节', version=2, confirmed_by='业务负责人'),
            dict(ref='https://example.invalid/sop', version=1, confirmed_by='业务负责人')]
        self.save()
        path = self.results_file()
        alias = path.parent / '中文证据.txt'
        alias.write_bytes((path.parent / 'evidence.txt').read_bytes())
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0].update(evidence=[alias.name, 'evidence.txt'], session='actual-session', finding='说明', note='附注')
        path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
        scenario_sha = hashlib.sha256(self.scenario.read_bytes()).hexdigest()
        results_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        expected_key = hashlib.sha256((scenario_sha + results_sha).encode()).hexdigest()
        result = self.cli('submit', self.scenario, '--results', path, '--implementer', '实现者')
        self.assertEqual(7, result['round'])
        self.assertEqual(statistics, result['statistics'])
        self.assertEqual(self.url + '/p/' + self.key + '/b/demo', result['board_url'])
        writes = [request for request in self.requests if request['method'] != 'GET']
        self.assertEqual(['PUT', 'POST', 'POST'], [request['method'] for request in writes])
        self.assertTrue(all(request['headers']['authorization_valid'] for request in writes))
        push, upload, round_request = writes
        body = json.loads(push['body'])
        expected_files = [dict(path=name, sha256=hashlib.sha256(content).hexdigest()) for name, content in [
            ('app.txt', b'version one\n'), ('docs/second.md', second_path.read_bytes()),
            ('docs/source.md', source_path.read_bytes())]]
        product_digest = hashlib.sha256(json.dumps(expected_files, sort_keys=True, ensure_ascii=False,
                                                  separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(dict(id='github.com/demo-org/demo-app', name='repo'), body['project'])
        for key, expected in [('path', 'docs/sop/demo.yaml'), ('commit', None), ('dirty', True),
                              ('product_digest', product_digest), ('pushed_by', '测试提交人'),
                              ('content', self.scenario.read_text()), ('entries', {'entries': {'cli': self.entry}})]:
            self.assertEqual(expected, body[key], key)
        self.assertEqual(result['fingerprints'], body['fingerprints'])
        self.assertEqual([dict(ref=self.doc['metadata']['sources'][0]['ref'], path='docs/source.md',
                               commit=None, sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                               confirmed_by='业务负责人', content=source_path.read_text())], body['sop_sources'])
        self.assertEqual(quote(alias.name, safe=''), upload['headers']['x-evidence-name'])
        self.assertEqual(alias.read_bytes(), upload['body'])
        round_body = json.loads(round_request['body'])
        self.assertEqual(expected_key, round_body['idempotency_key'])
        self.assertEqual(scenario_sha, round_body['scenario_file_sha256'])
        self.assertEqual(dict(commit=None, digest=product_digest, dirty=True), round_body['product'])
        self.assertEqual('实现者', round_body['implementer'])
        self.assertEqual('测试提交人', round_body['submitted_by'])
        for actual, original in zip(round_body['results'], rows):
            expected = dict(original, fingerprint=result['fingerprints'][original['scenario']],
                            evidence=[dict(name=name, sha256=hashlib.sha256(alias.read_bytes()).hexdigest())
                                      for name in original['evidence']])
            self.assertEqual(expected, actual)
        # The second identical submit has exactly the same idempotency key and no local history.
        self.cli('submit', self.scenario, '--results', path, '--implementer', '实现者')
        self.assertEqual(round_body, json.loads([r for r in self.requests if r['path'].endswith('/rounds')][-1]['body']))
        self.assertEqual(1, len(self.files(self.state)))  # Only the batch path binding is local.

    def test_pending_board_categories_latest_manual_and_missing_batch(self):
        """I3: local fingerprints, latest result, regression, and missing batches."""
        originals = [s for node in self.doc['sops'] for s in node['scenarios']]
        for index in range(4, 10):
            originals.append(dict(originals[0], id=f'X{index}'))
            self.doc['sops'][0]['scenarios'].append(originals[-1])
        originals[5]['regression'] = dict(check='unit', cases=['test_demo'])
        originals[8]['regression'] = dict(check='unit', cases=['test_demo'])
        originals[9]['regression'] = dict(check='unit', cases=['test_demo'])
        self.declare_check()
        self.save()
        statuses = [None, 'pass', None, 'fail', 'pass', 'pass', 'blocked', 'skip', 'pass', 'fail']
        remote = []
        for index, (scenario, status) in enumerate(zip(originals, statuses)):
            if index == 0:
                continue
            entry = dict(scenario=scenario['id'], fingerprint=fixtures.fingerprint(scenario),
                         status=status, queue='pending' if index in (2, 4, 5) else 'retest',
                         latest_agent=dict(status='pass', number=1) if status else None,
                         latest_manual=None)
            if index == 1:
                entry['fingerprint'] = 'old-fingerprint'
            if index in (3, 9):
                entry['latest_manual'] = dict(status=status, number=2, finding='人工最新结果')
            if index in (6, 7):
                entry['latest_agent'] = dict(status=status, number=2, finding='执行受阻')
            remote.append(entry)
        self.routes['GET', self.api + '/scenarios'] = (200, dict(ok=True, scenarios=remote))
        result = self.cli('pending', self.scenario)
        self.assertEqual(dict(zip([s['id'] for s in originals[:5]],
                                  ['new', 'changed', 'new', 'failed', 'source-changed'])) |
                         {originals[9]['id']: 'failed'},
                         {p['scenario']: p['reason'] for p in result['pending']})
        self.assertEqual([originals[i]['id'] for i in (5, 8)], [p['scenario'] for p in result['guarded']])
        self.assertTrue(all(p['check'] == 'unit' for p in result['guarded']))
        self.assertEqual([dict(scenario=originals[i]['id'], status=statuses[i], finding='执行受阻')
                          for i in (6, 7)], result['blocked'])
        output = self.cli('pending', self.scenario, fmt='text')
        for phrase in ('由回归守护', '受阻', 'source-changed', self.url + '/p/'):
            self.assertIn(phrase, output)
        for error_code in ('batch-not-found', 'project-not-found'):
            self.routes['GET', self.api + '/scenarios'] = (404, dict(ok=False, error_code=error_code, problems=[]))
            result = self.cli('pending', self.scenario)
            self.assertEqual(len(originals), len(result['pending']))
            self.assertEqual({'new'}, {p['reason'] for p in result['pending']})

    def test_pending_manual_blocked_latest_round_and_unpushed_product_warning(self):
        """I3 revision 2: latest round wins, manual blocked means failed, local changes warn."""
        scenarios = [s for node in self.doc['sops'] for s in node['scenarios']]
        rows = [dict(scenario=s['id'], fingerprint=fixtures.fingerprint(s), queue='retest',
                     status='pass', latest_agent=dict(status='pass', round=1), latest_manual=None)
                for s in scenarios]
        # Deliberately inconsistent status summary: use the actual latest result from the API.
        rows[0]['latest_manual'] = dict(status='blocked', round=2, finding='缺陷链接')
        rows[1].update(latest_agent=dict(status='fail', round=4), latest_manual=dict(status='pass', round=3))
        rows[2].update(latest_agent=dict(status='pass', round=6), latest_manual=dict(status='fail', round=5))
        self.routes['GET', self.api + '/scenarios'] = (200, dict(ok=True, scenarios=rows))
        self.routes['GET', self.api] = (200, dict(ok=True, product_digest='different-product'))
        result = self.cli('pending', self.scenario)
        self.assertEqual([dict(scenario=s['id'], reason='failed') for s in scenarios[:2]], result['pending'])
        self.assertEqual([], result['blocked'])
        self.assertIn('本机有未推送的产品改动，看板的待执行判断基于已推送的版本', result['warnings'])
        self.routes['GET', self.api] = (200, dict(ok=True, product_digest=result['product_fingerprint']))
        result = self.cli('pending', self.scenario)
        self.assertNotIn('本机有未推送', str(result['warnings']))

    def test_report_passes_through_markdown_and_json(self):
        """I3: both report formats use the board, and Markdown is byte-for-byte."""
        report = '# 看板报告\n\n一条已核对的结果。\n'
        self.routes['GET', self.api + '/report.md'] = (200, report.encode())
        self.routes['GET', self.api] = (200, dict(ok=True, round=12, queues={'pending': []}))
        self.env.pop('SOP_BOARD_TOKEN')
        self.assertEqual(report, self.cli('report', self.scenario, fmt=None))
        self.assertEqual(report, self.cli('report', self.scenario, fmt='markdown'))
        self.assertEqual(dict(ok=True, batch=dict(ok=True, round=12, queues={'pending': []})),
                         self.cli('report', self.scenario))
        for suffix, fmt in [('/report.md', 'markdown'), ('', 'json')]:
            self.routes['GET', self.api + suffix] = (404, dict(ok=False, error_code='batch-not-found', problems=[]))
            result = self.cli('report', self.scenario, fmt=fmt, code=1)
            if fmt == 'json':
                self.assertEqual('board-rejected', result['error_code'])
            else:
                self.assertIn('board-rejected', result)

    def test_board_rejections_and_non_json(self):
        """I1: HTTP 401/404/409/422 preserve board problems and classify non-JSON."""
        for status, error_code in [(401, 'unauthorized'), (404, 'task-not-found'),
                                   (409, 'scenario-stale'), (422, 'round-invalid')]:
            with self.subTest(status=status):
                problems = [dict(field='results[0].scenario', line=7, problem='看板拒绝此场景')]
                self.routes['GET', self.api + '/scenarios'] = (
                    status, dict(ok=False, error_code=error_code, problems=problems))
                result = self.cli('pending', self.scenario, code=1)
                self.assertEqual('board-rejected', result['error_code'])
                self.assertEqual([dict(line=None, problem='看板错误代码 ' + error_code),
                                  dict(line=7, problem='results[0].scenario：看板拒绝此场景')], result['problems'])
        self.routes['GET', self.api + '/scenarios'] = (200, b'<html>proxy error</html>')
        result = self.cli('pending', self.scenario, code=1)
        self.assertEqual('board-unavailable', result['error_code'])
        self.assertIn(self.url, str(result['problems']))

    def test_board_unreachable(self):
        """I1: connection failures identify the board address, with no traceback."""
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        self.env['SOP_BOARD_URL'] = f'http://127.0.0.1:{port}'
        result = self.cli('pending', self.scenario, code=1)
        self.assertEqual('board-unavailable', result['error_code'])
        self.assertIn(f':{port}', str(result['problems']))

    def test_pending_project_identity_variants(self):
        """I1/I3: remote normalization and project keys are visible in read URLs."""
        for remote in ['https://GitHub.COM/Demo-Org/Demo-App.git',
                       'git@GitHub.COM:Demo-Org/Demo-App.GIT',
                       'ssh://git@GitHub.COM:2222/Demo-Org/Demo-App.git',
                       'https://user@GitHub.COM:8443/Demo-Org/Demo-App']:
            with self.subTest(remote=remote):
                subprocess.run(['git', '-C', str(self.repo), 'remote', 'set-url', 'origin', remote],
                               check=True, env=self.env)
                result = self.cli('pending', self.scenario)
                self.assertTrue(any(r['path'] == self.api + '/scenarios' for r in self.requests))
                self.assertEqual(self.url + '/p/' + self.key + '/b/demo', result['board_url'])
                self.assertEqual([dict(scenario=s['id'], reason='new') for n in self.doc['sops']
                                  for s in n['scenarios']], result['pending'])
                self.assertFalse(self.requests[-1]['headers']['authorization_present'])
        for override in ('Custom.Host/Team__A/App', 'https://user@Custom.Host:8443/Team__A/App.GIT',
                         'git@Custom.Host:Team__A/App.git'):
            self.env['SOP_BOARD_PROJECT'] = override
            result = self.cli('pending', self.scenario)
            self.assertIn('/projects/custom-host-team-a-app/', self.requests[-1]['path'])
            self.assertIn('/p/custom-host-team-a-app/', result['board_url'])

    def test_project_identity_missing(self):
        """I1: no origin and no override fails before HTTP, but check stays local."""
        subprocess.run(['git', '-C', str(self.repo), 'remote', 'remove', 'origin'], check=True, env=self.env)
        result = self.cli('pending', self.scenario, code=1)
        self.assertEqual('project-identity-missing', result['error_code'])
        self.assertEqual([], self.requests)
        self.cli('check', self.scenario)


if __name__ == '__main__':
    unittest.main()
