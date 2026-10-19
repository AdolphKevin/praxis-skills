"""Public CLI contracts from SOP-VERIFY-3 revision 1, I1 / SOP-31."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest


SCRIPT = Path(__file__).resolve().with_name('sop.py')
PROJECT = 'github-com-demo-org-demo-app'
ATTENTION = '/api/v1/projects/' + PROJECT + '/attention'


def attention_items():
    """Eight literal examples from docs/sop/sop-verify-3.yaml."""
    return [dict(kind=kind, task=task, batch=batch, reason=reason,
                 url='http://board.example.test/p/' + PROJECT + suffix, resume=resume)
            for kind, task, batch, reason, suffix, resume in [
                ('developer-action', 12, 'demo', '方案待开发者批准', '/fixes?task=12', 'codex resume sess-12'),
                ('commit-needed', 13, 'demo', '工作区有未提交的产品改动', '/b/demo/runs?task=13', ''),
                ('developer-merge', 14, 'demo', '基线已前进且合入有冲突', '/fixes?task=14', 'codex resume sess-14'),
                ('cases-needed', 15, 'refund', '用例 TC_REFUND_FLOW_003 缺少预期结果', '/b/refund/merges?task=15', ''),
                ('sync-needed', 16, 'refund', '合并结果待取回仓库', '/b/refund/merges?task=16', ''),
                ('jira-manual', 17, 'demo', 'Jira 单 DEMO-7 流转失败', '/fixes?task=17', ''),
                ('interrupted', 18, 'demo', '看板重启时会话中断', '/fixes?task=18', 'codex resume sess-18'),
                ('developer-action', 19, 'refund', '连续三次尝试未通过', '/fixes?task=19', 'codex resume sess-19'),
            ]]


class StatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sop-status-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.repo = self.base / 'demo-app'
        self.repo.mkdir()
        # Allow only process-launch settings; never inherit real board credentials.
        self.env = {name: os.environ[name] for name in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TMPDIR')
                    if name in os.environ}
        self.env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                        GIT_OPTIONAL_LOCKS='0', XDG_STATE_HOME=str(self.base / 'state'))
        self.git('init', '-q')
        self.git('remote', 'add', 'origin', 'https://github.com/demo-org/demo-app.git')
        self.requests = []
        self.response = (200, dict(ok=True, items=[]))
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def handle_request(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                owner.requests.append(dict(method=self.command, path=self.path, body=body,
                    authorization_present='Authorization' in self.headers))
                response = owner.response() if callable(owner.response) else owner.response
                status, value = response
                payload = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            do_GET = do_POST = do_PUT = do_DELETE = handle_request

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_board)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.env['SOP_BOARD_URL'] = self.url

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout

    def close_board(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def snapshot(self):
        return {str(path.relative_to(self.base)): path.read_bytes() if path.is_file() else None
                for path in self.base.rglob('*')}

    def cli(self, *args, code=0, cwd=None, timeout=40):
        before = self.snapshot()
        git_status = self.git('status', '--porcelain')
        process = subprocess.run([sys.executable, str(SCRIPT), 'status', *map(str, args)],
                                 cwd=cwd or self.repo, env=self.env, capture_output=True,
                                 text=True, timeout=timeout)
        combined = process.stdout + process.stderr
        token = self.env.get('SOP_BOARD_TOKEN', '')
        self.assertFalse(token and token in combined, '测试令牌出现在命令输出')
        safe_output = combined.replace(token, '***') if token else combined
        self.assertEqual(code, process.returncode, safe_output)
        self.assertEqual('', process.stderr, safe_output)
        self.assertEqual(before, self.snapshot(), 'status 修改了文件或新建了目录')
        self.assertEqual(git_status, self.git('status', '--porcelain'))
        return json.loads(process.stdout) if '--format' in args and args[args.index('--format') + 1] == 'json' else process.stdout

    def test_unconfigured_board_is_empty_without_requests(self):
        """SOP-31-P01: unset and empty URLs are successful, exact, and read-only."""
        self.git('remote', 'remove', 'origin')
        for value in (None, ''):
            with self.subTest(url=value):
                if value is None:
                    self.env.pop('SOP_BOARD_URL', None)
                else:
                    self.env['SOP_BOARD_URL'] = value
                self.assertEqual('未配置看板（SOP_BOARD_URL），没有看板上的待处理事项\n', self.cli())
                self.assertEqual(dict(ok=True, board=None, items=[]), self.cli('--format', 'json'))
        self.assertEqual([], self.requests)

    def test_json_preserves_items_and_uses_one_project_get(self):
        """SOP-31-P03/P06: raw items, normalized address, one unauthenticated GET."""
        items = attention_items()
        items[0]['future_field'] = {'retained': True}
        self.response = 200, dict(ok=True, items=items)
        self.env['SOP_BOARD_URL'] += '/'
        self.assertEqual(dict(ok=True, board=self.url, project=PROJECT, items=items),
                         self.cli('--format', 'json'))
        self.assertEqual([dict(method='GET', path=ATTENTION, body=b'', authorization_present=False)],
                         self.requests)

    def test_text_groups_seven_kinds_in_order_and_preserves_order_within_group(self):
        """SOP-31-P02: every field, one group per kind, and only nonempty resumes."""
        items = attention_items()
        self.response = 200, dict(ok=True, items=items)
        output = self.cli()
        headings = ['待开发者处理', '待开发者合入', '待提交', '待补充', '待同步',
                    'Jira 状态待人工更新', '已中断']
        self.assertEqual(headings, [line.rstrip('：') for line in output.splitlines()
                                    if line.rstrip('：') in headings])
        self.assertEqual(['12', '19', '14', '13', '15', '16', '17', '18'],
                         re.findall(r'任务：(\d+)', output))
        for item in items:
            self.assertNotIn(item['kind'], output)
            self.assertEqual(1, output.count(item['reason']))
            self.assertEqual(1, output.count(item['url']))
            task_start = output.index('任务：' + str(item['task']))
            task_end = output.find('任务：', task_start + 1)
            section = output[task_start:task_end] if task_end != -1 else output[task_start:]
            # The batch is on the same item line, before the task number.
            line = next(line for line in output.splitlines() if '任务：' + str(item['task']) in line)
            self.assertIn(item['batch'], line)
            self.assertIn(item['reason'], section)
            self.assertIn(item['url'], section)
            if item['resume']:
                self.assertIn('接续：' + item['resume'], section)
            else:
                self.assertNotIn('接续：', section)
        self.assertEqual(4, output.count('接续：'))

    def test_unknown_kinds_follow_known_groups_and_project_items_have_no_resume(self):
        """I1 / SOP-31-P02/P03: unknown kinds, absent/empty batches and sessions."""
        items = [dict(kind='future-z', task=90, reason='项目任务', url='http://board.test/90'),
                 attention_items()[6],
                 dict(kind='future-a', task=91, batch='', reason='没有会话', url='http://board.test/91', resume=''),
                 dict(kind='future-z', task=92, batch=None, reason='另一项目任务', url='http://board.test/92', resume=None)]
        self.response = 200, dict(ok=True, items=items)
        output = self.cli()
        self.assertEqual(['已中断', 'future-z', 'future-a'],
                         [line.rstrip('：') for line in output.splitlines() if line and not line[0].isspace()])
        self.assertEqual(['18', '90', '92', '91'], re.findall(r'任务：(\d+)', output))
        self.assertEqual(3, output.count('项目级'))
        self.assertEqual(1, output.count('接续：'))
        self.assertIn('接续：codex resume sess-18', output)
        self.assertEqual(items, self.cli('--format', 'json')['items'])

    def test_empty_board_has_no_groups(self):
        """SOP-31-P04: configured empty boards have a distinct message and JSON."""
        self.assertEqual('看板上没有待开发者处理的事项\n', self.cli())
        self.assertEqual(dict(ok=True, board=self.url, project=PROJECT, items=[]),
                         self.cli('--format', 'json'))

    def test_missing_project_is_successful_and_explained(self):
        """SOP-31-N01: only 404 project-not-found becomes a successful empty result."""
        self.response = 404, dict(ok=False, error_code='project-not-found', problems=['项目不存在'])
        output = self.cli()
        self.assertIn('看板上还没有项目 ' + PROJECT, output)
        self.assertNotIn('board-rejected', output)
        result = self.cli('--format', 'json')
        self.assertTrue(result['ok'])
        self.assertEqual([], result['items'])
        self.assertEqual(self.url, result['board'])
        self.assertEqual(PROJECT, result['project'])

    def test_non_json_response_names_address_and_reason(self):
        """SOP-31-N03: HTML is unavailable, never an empty success."""
        self.response = 200, b'<html>not JSON</html>'
        for options in ((), ('--format', 'json')):
            with self.subTest(options=options):
                result = self.cli(*options, code=1)
                text = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
                self.assertIn('board-unavailable', text)
                self.assertIn(self.url + ATTENTION, text)
                self.assertIn('响应不是 JSON', text)
                self.assertNotIn('看板上没有待开发者处理的事项', text)
                if isinstance(result, dict):
                    self.assertFalse(result['ok'])
                    self.assertEqual('board-unavailable', result['error_code'])

    def test_project_identity_and_override_choose_request_path(self):
        """SOP-31-P05: SSH origin and the explicit URL override share normalization."""
        self.git('remote', 'set-url', 'origin', 'git@github.com:Demo-Org/demo-app.git')
        self.assertEqual(PROJECT, self.cli('--format', 'json')['project'])
        self.env['SOP_BOARD_PROJECT'] = 'https://GitLab.Example.com/Team/Other-App.git'
        self.assertEqual('gitlab-example-com-team-other-app', self.cli('--format', 'json')['project'])
        self.assertEqual([ATTENTION, '/api/v1/projects/gitlab-example-com-team-other-app/attention'],
                         [request['path'] for request in self.requests])

    def test_token_is_optional_never_sent_and_never_printed(self):
        """SOP-31-P06: four read-only calls work with/without a generated test token."""
        self.response = 200, dict(ok=True, items=attention_items())
        # Even an unusable state location is irrelevant to this read-only command.
        self.env['SOP_VERIFY_STATE'] = str(self.repo / 'must-not-be-created')
        for token in ('', secrets.token_hex(24)):
            if token:
                self.env['SOP_BOARD_TOKEN'] = token
            else:
                self.env.pop('SOP_BOARD_TOKEN', None)
            output = self.cli()
            self.assertEqual(8, len(re.findall(r'任务：(\d+)', output)))
            self.assertEqual(attention_items(), self.cli('--format', 'json')['items'])
        self.assertEqual(4, len(self.requests))
        self.assertTrue(all(request['method'] == 'GET' and not request['authorization_present']
                            for request in self.requests))

    def test_echoed_test_token_is_redacted_in_success_and_failure(self):
        """I1 / SOP-31-P06: even board-provided text cannot expose the test token."""
        token = secrets.token_hex(24)
        self.env['SOP_BOARD_TOKEN'] = token
        item = dict(kind='developer-action', task=1, batch='', reason=token,
                    url='http://board.test/' + token, resume='codex resume ' + token)
        self.response = 200, dict(ok=True, items=[item])
        self.assertIn('***', self.cli())
        self.assertEqual('***', self.cli('--format', 'json')['items'][0]['reason'])
        self.response = 500, dict(ok=False, error_code='internal-error',
                                 problems=[dict(field='items', problem=token)])
        self.assertIn('***', self.cli(code=1))
        self.assertEqual(dict(line=None, problem='items：***'),
                         self.cli('--format', 'json', code=1)['problems'][1])

    def test_other_board_rejections_preserve_error_codes_and_problem_fields(self):
        """SOP-31-N04: 500 and non-project 404 remain failures with exact problems."""
        for status, error, problems in [
            (500, 'internal-error', [dict(field='items', problem='读取失败')]),
            (404, 'batch-not-found', []),
            (403, 'project-not-found', []),
            (200, 'internal-error', [dict(field='items', line=7, problem='读取失败')]),
        ]:
            with self.subTest(status=status, error=error):
                self.response = status, dict(ok=False, error_code=error, problems=problems)
                result = self.cli('--format', 'json', code=1)
                expected = [dict(line=None, problem='看板错误代码 ' + error)]
                if problems:
                    expected.append(dict(line=problems[0].get('line'), problem='items：读取失败'))
                self.assertEqual(dict(ok=False, error_code='board-rejected', problems=expected), result)
                output = self.cli(code=1)
                self.assertIn('board-rejected', output)
                self.assertIn('看板错误代码 ' + error, output)

    def test_unreachable_board_names_address_and_connection_reason(self):
        """SOP-31-N02: connection refusal is an explained error in both formats."""
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            address = f'http://127.0.0.1:{listener.getsockname()[1]}'
        self.env['SOP_BOARD_URL'] = address
        output = self.cli(code=1)
        result = self.cli('--format', 'json', code=1)
        self.assertIn('board-unavailable', output)
        self.assertFalse(result['ok'])
        self.assertEqual('board-unavailable', result['error_code'])
        for text in (output, json.dumps(result, ensure_ascii=False)):
            self.assertIn(address, text)
            self.assertRegex(text.lower(), 'refused|拒绝')
            self.assertNotIn('未配置看板', text)
            self.assertNotIn('看板上没有待开发者处理的事项', text)
        self.assertEqual([], self.requests)

    def test_missing_identity_fails_before_request(self):
        """SOP-31-N05: no origin or override means no guessed identity and no HTTP."""
        self.git('remote', 'remove', 'origin')
        result = self.cli('--format', 'json', code=1)
        self.assertFalse(result['ok'])
        self.assertEqual('project-identity-missing', result['error_code'])
        self.assertIn('project-identity-missing', self.cli(code=1))
        self.assertEqual([], self.requests)

    def test_outside_git_fails_even_without_a_board(self):
        """I1: status needs a Git repository, independently of board configuration."""
        for configured in (True, False):
            with self.subTest(configured=configured):
                if not configured:
                    self.env.pop('SOP_BOARD_URL')
                result = self.cli('--format', 'json', cwd=self.base, code=1)
                self.assertFalse(result['ok'])
                self.assertEqual('not-a-git-repository', result['error_code'])
        self.assertEqual([], self.requests)

    def test_explicit_root_needs_no_scenario_files(self):
        """I1: --root works from outside a repository that contains no docs/sop."""
        self.assertFalse((self.repo / 'docs').exists())
        self.assertEqual(dict(ok=True, board=self.url, project=PROJECT, items=[]),
                         self.cli('--root', self.repo, '--format', 'json', cwd=self.base))

    def test_timeout_is_thirty_seconds(self):
        """SOP-31-N03: an actual stalled HTTP request times out before 40 seconds."""
        release = threading.Event()
        self.addCleanup(release.set)

        def stall():
            release.wait(40)
            return 200, dict(ok=True, items=[])

        self.response = stall
        started = time.monotonic()
        result = self.cli('--format', 'json', code=1, timeout=39)
        elapsed = time.monotonic() - started
        self.assertFalse(result['ok'])
        self.assertEqual('board-unavailable', result['error_code'])
        self.assertIn(self.url + ATTENTION, str(result['problems']))
        self.assertIn('timed out', str(result['problems']))
        self.assertGreaterEqual(elapsed, 29)
        self.assertLess(elapsed, 39)
        self.assertEqual(1, len(self.requests))


if __name__ == '__main__':
    unittest.main()
