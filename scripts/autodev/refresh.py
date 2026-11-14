"""Trusted-main controller. Never imports, checks out or executes PR code."""
import json
import re
import subprocess
from urllib.parse import quote

REPO = 'wondersonrj/huginn-ia'
ROOT = f'repos/{REPO}'
WORKFLOW = 'autodev-revalidate.yml'


class ApiError(Exception):
    pass


def api(path, method='GET', data=None):
    args = ['gh', 'api', f'{ROOT}/{path}', '--method', method]
    if data is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None,
                            capture_output=True, text=True, check=False)
    if result.returncode:
        # Deliberately exclude response bodies, tokens and logs from diagnostics.
        raise ApiError('GitHub API rejected request; inspect repository Actions metadata')
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(path, key=None):
    result = []
    page = 1
    while True:
        value = api(f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')
        items = value[key] if key else value
        result.extend(items)
        if len(items) < 100:
            return result
        page += 1


def eligible(pr):
    return (pr['state'] == 'open' and not pr['draft']
            and pr['head']['repo'] is not None
            and pr['head']['repo']['full_name'] == REPO
            and pr['base']['repo']['full_name'] == REPO
            and pr['base']['ref'] == 'main'
            and pr['head']['ref'] != 'main')


def notify(number, head, base, reason):
    marker = f'<!-- autodev:{head}:{base}:{reason} -->'
    if any(marker in (c.get('body') or '') for c in pages(f'issues/{number}/comments')):
        return
    api(f'issues/{number}/comments', 'POST', {'body':
        f'{marker}\nAutoDev: {reason}. Head `{head}`, main `{base}`. '
        'Revise conflitos/permissões e os metadados de Actions. '
        'Nenhum force-push, merge de PR ou deploy foi realizado. '
        'Após corrigir uma falha, envie novo commit para uma nova validação.'})


def refresh(number, base, runs):
    pr = api(f'pulls/{number}')
    if not eligible(pr):
        return
    head = pr['head']['sha']
    comparison = api(f'compare/{base}...{head}')
    if comparison['behind_by']:
        if pr['mergeable'] is None:
            return  # GitHub still computing mergeability; next scheduled pass retries.
        if not pr['mergeable']:
            notify(number, head, base, 'conflito requer resolução humana')
            return
        # Lease prevents overwriting concurrent contributor changes; no force/rebase.
        api(f'pulls/{number}/update-branch', 'PUT', {'expected_head_sha': head})
        return  # Asynchronous API: re-fetch and validate ancestry on the next pass.
    if api('git/ref/heads/main')['object']['sha'] != base:
        return
    current = api(f'pulls/{number}')
    if not eligible(current) or current['head']['sha'] != head:
        return
    identity = f'autodev-{number}-{head}-{base}'
    matching = [r for r in runs if r['display_title'] == identity
                and r['event'] == 'workflow_dispatch' and r['head_branch'] == 'main'
                and r['head_sha'] == base
                and r['path'] == f'.github/workflows/{WORKFLOW}'
                and r['actor']['login'] == 'github-actions[bot]']
    if not matching:
        api(f'actions/workflows/{WORKFLOW}/dispatches', 'POST',
            {'ref': 'main', 'inputs': {'pr': str(number), 'head': head, 'base': base}})
        return
    run = max(matching, key=lambda r: r['id'])
    if run['status'] != 'completed':
        return
    jobs = pages(f'actions/runs/{run["id"]}/jobs?filter=latest', 'jobs')
    # Require actual tests, not just a green workflow or skipped jobs.
    expected = {'portable', 'Backend tests (Python 3.12)',
                'Frontend build (Node 20)', 'Dependency audit'}
    passed = {j['name'].split(' / ')[-1] for j in jobs if j['conclusion'] == 'success'}
    success = run['conclusion'] == 'success' and expected <= passed
    state = 'success' if success else 'failure'
    url = f'https://github.com/{REPO}/actions/runs/{run["id"]}'
    statuses = pages(f'commits/{head}/statuses')
    if not any(s['context'] == 'portable' and s['state'] == state
               and s.get('target_url') == url for s in statuses):
        # This is an actual result from immutable read-only tests, never a synthetic pass.
        api(f'statuses/{head}', 'POST', {'context': 'portable', 'state': state,
            'target_url': url, 'description': 'AutoDev immutable Windows + quality validation'})
    if not success:
        notify(number, head, base, f'validação falhou; execução {run["id"]}')


def main():
    base = api('git/ref/heads/main')['object']['sha']
    if not re.fullmatch(r'[0-9a-f]{40}', base):
        raise ValueError('Invalid main SHA')
    runs = pages(f'actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch', 'workflow_runs')
    for pr in pages('pulls?state=open&base=main'):
        if not eligible(pr):
            continue
        try:
            refresh(pr['number'], base, runs)
        except ApiError:
            notify(pr['number'], pr['head']['sha'], base, 'API recusou atualização ou revalidação')


if __name__ == '__main__':
    main()
