"""API contract tests: no network, credentials or PR code execution."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest

spec = importlib.util.spec_from_file_location('refresh', Path(__file__).parents[2] / 'scripts/autodev/refresh.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
HEAD, BASE = 'a' * 40, 'b' * 40


def pr(**overrides):
    return dict(state='open', draft=False, number=7, mergeable=True,
                head={'sha': HEAD, 'ref': 'feature', 'repo': {'full_name': m.REPO}},
                base={'ref': 'main', 'repo': {'full_name': m.REPO}}, **overrides)


def fixture_api(monkeypatch, behind=0, pull=None, jobs=None, statuses=None):
    def call(path, method='GET', data=None):
        if method != 'GET':
            return None
        if path == 'pulls/7':
            return pull or pr()
        if path.startswith('compare/'):
            return {'behind_by': behind}
        if path == 'git/ref/heads/main':
            return {'object': {'sha': BASE}}
        raise AssertionError(path)
    mock = Mock(side_effect=call)
    monkeypatch.setattr(m, 'api', mock)
    monkeypatch.setattr(m, 'pages', lambda path, key=None: jobs if '/jobs?' in path else (statuses or []))
    return mock


def run(conclusion='success'):
    return dict(id=123, display_title=f'autodev-7-{HEAD}-{BASE}', event='workflow_dispatch',
                head_branch='main', head_sha=BASE, path=f'.github/workflows/{m.WORKFLOW}',
                actor={'login': 'github-actions[bot]'}, status='completed', conclusion=conclusion)


def jobs():
    return [dict(name='group / ' + name, conclusion='success') for name in
            ['portable', 'Backend tests (Python 3.12)', 'Frontend build (Node 20)', 'Dependency audit']]


def writes(mock):
    return [c.args for c in mock.call_args_list if len(c.args) > 1]


def test_update_has_lease_and_waits(monkeypatch):
    mock = fixture_api(monkeypatch, behind=1)
    m.refresh(7, BASE, [])
    assert writes(mock) == [('pulls/7/update-branch', 'PUT', {'expected_head_sha': HEAD})]


@pytest.mark.parametrize('mergeable', [False, None])
def test_conflict_or_pending_never_updates(monkeypatch, mergeable):
    pull = pr(); pull['mergeable'] = mergeable
    mock = fixture_api(monkeypatch, behind=1, pull=pull)
    m.refresh(7, BASE, [])
    assert not any('/update-branch' in c[0] for c in writes(mock))
    assert bool(writes(mock)) == (mergeable is False)


def test_fork_never_writes(monkeypatch):
    pull = pr(); pull['head']['repo']['full_name'] = 'attacker/fork'
    mock = fixture_api(monkeypatch, pull=pull)
    m.refresh(7, BASE, [])
    assert writes(mock) == []


def test_explicit_dispatch_main_immutable_input(monkeypatch):
    mock = fixture_api(monkeypatch)
    m.refresh(7, BASE, [])
    assert writes(mock) == [(f'actions/workflows/{m.WORKFLOW}/dispatches', 'POST',
                            {'ref': 'main', 'inputs': {'pr': '7', 'head': HEAD, 'base': BASE}})]


def test_running_is_idempotent(monkeypatch):
    mock = fixture_api(monkeypatch)
    r = run(); r['status'] = 'in_progress'
    m.refresh(7, BASE, [r])
    assert writes(mock) == []


def test_real_success_on_correct_sha(monkeypatch):
    mock = fixture_api(monkeypatch, jobs=jobs())
    m.refresh(7, BASE, [run()])
    assert writes(mock)[0][0] == f'statuses/{HEAD}'
    assert writes(mock)[0][2]['state'] == 'success'


def test_skipped_portable_cannot_pass(monkeypatch):
    mock = fixture_api(monkeypatch, jobs=jobs()[1:])
    m.refresh(7, BASE, [run()])
    assert writes(mock)[0][2]['state'] == 'failure'
    assert writes(mock)[1][0] == 'issues/7/comments'


def test_failure_never_retries_same_tuple(monkeypatch):
    mock = fixture_api(monkeypatch, jobs=jobs())
    m.refresh(7, BASE, [run('failure')])
    assert not any('dispatches' in c[0] for c in writes(mock))
    assert writes(mock)[0][2]['state'] == 'failure'


def test_report_idempotent(monkeypatch):
    status = dict(context='portable', state='success', target_url=f'https://github.com/{m.REPO}/actions/runs/123')
    mock = fixture_api(monkeypatch, jobs=jobs(), statuses=[status])
    m.refresh(7, BASE, [run()])
    assert writes(mock) == []


def test_api_lease_rejection_not_force_retried(monkeypatch):
    mock = fixture_api(monkeypatch, behind=1)
    original = mock.side_effect
    def reject(path, method='GET', data=None):
        if method == 'PUT':
            raise m.ApiError('lease rejected')
        return original(path, method, data)
    mock.side_effect = reject
    with pytest.raises(m.ApiError):
        m.refresh(7, BASE, [])
    assert len(writes(mock)) == 1


def test_stale_or_forged_run_not_reported(monkeypatch):
    mock = fixture_api(monkeypatch, jobs=jobs())
    stale = run(); stale['head_sha'] = HEAD
    forged = run(); forged['actor'] = {'login': 'attacker'}
    m.refresh(7, BASE, [stale, forged])
    assert all(not c[0].startswith('statuses/') for c in writes(mock))
