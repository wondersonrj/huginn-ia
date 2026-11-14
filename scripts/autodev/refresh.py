"""Trusted-main controller. Never imports, checks out or executes PR code."""
import json
import os
import re
import subprocess

REPO = 'wondersonrj/huginn-ia'
ROOT = f'repos/{REPO}'
WORKFLOW = 'autodev-revalidate.yml'
PR_WORKFLOWS = {'autodev-quality.yml', WORKFLOW, 'windows-portable.yml'}
APPROVAL_GUIDANCE = (
    'O proprietário/mantenedor deve revisar o diff e os workflows do PR no SHA indicado, '
    'abrir os runs vinculados e clicar em Approve and run workflows '
    '(Aprovar e executar workflows), se essa opção for exibida. '
    'Não alterar Settings/Actions ou rulesets. A automação não aprova runs '
    'nem dispara uma validação alternativa enquanto este bloqueio existir.'
)


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


def notify(number, head, base, reason, guidance=None):
    marker = f'<!-- autodev:{head}:{base}:{reason} -->'
    if any(marker in (c.get('body') or '') for c in pages(f'issues/{number}/comments')):
        return
    api(f'issues/{number}/comments', 'POST', {'body':
        f'{marker}\nAutoDev: {reason}. Head `{head}`, main `{base}`. '
        'Revise conflitos/permissões e os metadados de Actions. '
        'Nenhum force-push, merge de PR ou deploy foi realizado. '
        + (guidance or 'Após corrigir uma falha, envie novo commit para uma nova validação.')})


def approval_blockers(number, head):
    """Only current internal PR runs; never infer approval from empty jobs/statuses."""
    runs = pages(f'actions/runs?event=pull_request&head_sha={head}', 'workflow_runs')
    return [r for r in runs
            if r['event'] == 'pull_request' and r['head_sha'] == head
            and r['path'] in {f'.github/workflows/{p}' for p in PR_WORKFLOWS}
            and r['conclusion'] == 'action_required'
            and any(p['number'] == number
                    and p['head']['sha'] == head
                    and p['head']['repo']['id'] == p['base']['repo']['id']
                    for p in r['pull_requests'])]


def pause_for_approval(number, head, base, runs):
    links = ', '.join(f'https://github.com/{REPO}/actions/runs/{r["id"]}'
                      for r in sorted(runs, key=lambda r: r['id']))
    notify(number, head, base, 'action_required; aprovação humana necessária',
           f'{APPROVAL_GUIDANCE} Execuções: {links}')
    return 'approval_required'


def report(number, outcome):
    # Fixed outcomes and numeric PR IDs only: no PR titles, bodies or raw API errors.
    line = f'PR #{number}: {outcome}'
    print(line, flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write(line + '\n\n')


def refresh(number, base, runs):
    pr = api(f'pulls/{number}')
    if not eligible(pr):
        return
    head = pr['head']['sha']
    blockers = approval_blockers(number, head)
    if blockers:
        return pause_for_approval(number, head, base, blockers)
    comparison = api(f'compare/{base}...{head}')
    if comparison['behind_by']:
        if pr['mergeable'] is None:
            return  # GitHub still computing mergeability; next scheduled pass retries.
        if not pr['mergeable']:
            notify(number, head, base, 'conflito requer resolução humana')
            return
        # Lease prevents overwriting concurrent contributor changes; no force/rebase.
        api(f'pulls/{number}/update-branch', 'PUT', {'expected_head_sha': head})
        return 'update_requested; validation_not_dispatched'  # API is asynchronous.
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
        return 'dispatch_requested; tests_not_yet_verified'
    run = max(matching, key=lambda r: r['id'])
    if run['conclusion'] == 'action_required':
        return pause_for_approval(number, head, base, [run])
    if run['status'] != 'completed':
        return 'validation_in_progress'
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
    return 'validation_success' if success else 'validation_failure'


def main():
    base = api('git/ref/heads/main')['object']['sha']
    if not re.fullmatch(r'[0-9a-f]{40}', base):
        raise ValueError('Invalid main SHA')
    runs = pages(f'actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch', 'workflow_runs')
    errors = False
    for pr in pages('pulls?state=open&base=main'):
        if not eligible(pr):
            continue
        try:
            outcome = refresh(pr['number'], base, runs)
            report(pr['number'], outcome or 'deferred_or_ineligible')
        except ApiError:
            errors = True
            report(pr['number'], 'api_error; inspect Actions metadata')
            notify(pr['number'], pr['head']['sha'], base, 'API recusou atualização ou revalidação')
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
