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


def fixture_api(monkeypatch, behind=0, pull=None, jobs=None, statuses=None, pr_runs=None):
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
    def paginated(path, key=None):
        if '/jobs?' in path:
            return jobs
        if path.startswith('actions/runs?event=pull_request'):
            return pr_runs or []
        if path.endswith('/statuses'):
            return statuses or []
        return []
    monkeypatch.setattr(m, 'pages', paginated)
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


def blocked_pr_run(run_id=456):
    return dict(id=run_id, event='pull_request', head_sha=HEAD,
                path='.github/workflows/autodev-quality.yml', conclusion='action_required',
                pull_requests=[dict(number=7, head={'sha': HEAD, 'repo': {'id': 1}},
                                    base={'repo': {'id': 1}})])


def test_pr_approval_stops_before_update_dispatch_or_status(monkeypatch):
    mock = fixture_api(monkeypatch, behind=1, pr_runs=[blocked_pr_run()])
    assert m.refresh(7, BASE, []) == 'approval_required'
    changes = writes(mock)
    assert len(changes) == 1 and changes[0][0] == 'issues/7/comments'
    assert 'Approve and run workflows' in changes[0][2]['body']
    assert '/actions/runs/456' in changes[0][2]['body']
    assert not any(c.args[0].startswith('compare/') for c in mock.call_args_list)


def test_dispatch_approval_is_not_a_test_failure_or_retried(monkeypatch):
    mock = fixture_api(monkeypatch)
    assert m.refresh(7, BASE, [run('action_required')]) == 'approval_required'
    assert len(writes(mock)) == 1
    assert writes(mock)[0][0] == 'issues/7/comments'


@pytest.mark.parametrize('field,value', [('head_sha', BASE), ('event', 'push'),
                                      ('path', '.github/workflows/unrelated.yml'),
                                      ('conclusion', 'success')])
def test_unrelated_or_approved_pr_runs_do_not_block(monkeypatch, field, value):
    r = blocked_pr_run(); r[field] = value
    mock = fixture_api(monkeypatch, pr_runs=[r])
    assert m.refresh(7, BASE, []) == 'dispatch_requested; tests_not_yet_verified'
    assert writes(mock)[0][0].endswith('/dispatches')


@pytest.mark.parametrize('other_pr,fork', [(8, False), (7, True)])
def test_other_pr_or_fork_approval_is_not_current_approval(monkeypatch, other_pr, fork):
    r = blocked_pr_run(); r['pull_requests'][0]['number'] = other_pr
    if fork:
        r['pull_requests'][0]['head']['repo']['id'] = 2
    mock = fixture_api(monkeypatch, pr_runs=[r])
    m.refresh(7, BASE, [])
    assert writes(mock)[0][0].endswith('/dispatches')


def test_approval_comment_is_deduplicated(monkeypatch):
    mock = fixture_api(monkeypatch, pr_runs=[blocked_pr_run()])
    m.refresh(7, BASE, [])
    body = writes(mock)[0][2]['body']
    saved_pages = m.pages
    monkeypatch.setattr(m, 'pages', lambda path, key=None:
                        [{'body': body}] if path.endswith('/comments') else saved_pages(path, key))
    mock.reset_mock()
    m.refresh(7, BASE, [])
    assert writes(mock) == []


def test_approval_then_approved_real_jobs_resume(monkeypatch):
    fixture_api(monkeypatch, pr_runs=[blocked_pr_run()])
    assert m.refresh(7, BASE, []) == 'approval_required'
    approved = blocked_pr_run(); approved['conclusion'] = 'success'
    mock = fixture_api(monkeypatch, jobs=jobs(), pr_runs=[approved])
    assert m.refresh(7, BASE, [run()]) == 'validation_success'
    assert writes(mock)[0][2]['state'] == 'success'


def test_api_error_is_not_silent_success(monkeypatch):
    def get(path, method='GET', data=None):
        return {'object': {'sha': BASE}}
    monkeypatch.setattr(m, 'api', get)
    monkeypatch.setattr(m, 'pages', lambda path, key=None: [] if key == 'workflow_runs' else [pr()])
    monkeypatch.setattr(m, 'refresh', Mock(side_effect=m.ApiError('denied')))
    notify = Mock(); monkeypatch.setattr(m, 'notify', notify)
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 1
    notify.assert_called_once()


def test_summary_distinguishes_controller_from_test_result(monkeypatch, tmp_path, capsys):
    summary = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    m.report(7, 'approval_required')
    assert 'PR #7: approval_required' in summary.read_text()
    assert 'approval_required' in capsys.readouterr().out
