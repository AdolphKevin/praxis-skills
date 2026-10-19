"""Retrieve a completed board merge without overwriting local edits."""
from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from _board import Board
from _contracts import Invalid, load_document, problem, resolve_entries, validate_scenarios
from _state import digest


def pull(root, path, batch, pairs_path):
    if not os.environ.get('SOP_BOARD_URL'):
        raise Invalid('board-not-configured', [problem('pull 需要设置 SOP_BOARD_URL')])
    try:
        local = path.read_bytes() if path.exists() else None
    except OSError as error:
        raise Invalid('scenario-file-invalid', [problem(str(error))]) from error
    if local is not None:
        document = load_document(path, 'scenario-file-invalid', local)
        metadata = document.get('metadata') if isinstance(document, dict) else None
        if not isinstance(metadata, dict) or not isinstance(metadata.get('batch'), str) or not metadata['batch'].strip():
            raise Invalid('scenario-file-invalid', [problem('场景文件缺少 metadata.batch')])
        batch = metadata['batch']
    board = Board(root, batch)
    response = board.request('/api/v1/tasks?' + urlencode(dict(project=board.key, batch=batch)))
    tasks = [task for task in response['tasks'] if task['kind'] == 'merge' and task['status'] == '已完成']
    if not tasks:
        raise Invalid('merge-not-found', [problem(f'批次 {batch} 没有已完成的合并任务')])
    task = max(tasks, key=lambda item: int(item['id']))
    number = task['id']
    merged = board.request(board.api + f'/merges/{number}/scenario-file', raw_response=True).encode('utf-8')
    local_sha = digest(local) if local is not None else ''
    if local_sha != task['scenario_file_sha256'] and local != merged:
        raise Invalid('pull-conflict', [problem('本地场景文件已修改，请先 submit 推送后由看板重新合并')])
    pairs = board.request(board.api + f'/merges/{number}/pairs.json')
    # A downloaded scenario must pass the same local contract as a subsequent check.
    document = load_document(path, 'scenario-file-invalid', merged)
    entries, _, _ = resolve_entries(root, path)
    validate_scenarios(document, entries['entries'], entries.get('checks'))
    written = []
    if local != merged:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(merged)
        written.append(str(path))
    if pairs_path is not None:
        pairs_path.parent.mkdir(parents=True, exist_ok=True)
        pairs_path.write_text(json.dumps(pairs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        written.append(str(pairs_path))
    return dict(ok=True, written=written, task=number,
                pairs_count=sum(len(pairs.get(key, [])) for key in ('covered', 'conflict', 'disposed')))
