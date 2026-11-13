"""One-time administrative preparation. No private material in files/logs/outputs.
Additive rulesets, reviewer preservation and fail-closed secret reuse.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY='wondersonrj/huginn-ia'
BASE=f'/repos/{REPOSITORY}'
BOOTSTRAP='distribution-bootstrap'
TEST='windows-release-teste'
RECOVERY='windows-signing-recovery'
ADMIN_SECRET='HUGINN_DISTRIBUTION_ADMIN_TOKEN'
SIGNING_SECRET='HUGINN_RELEASE_SIGNING_KEY'
RECOVERY_SECRET='HUGINN_TEST_SIGNING_KEY_RECOVERY'
PUBLIC_FILE='packaging/windows/release-public-keys.json'


class PreparationError(Exception):pass


class API:
    def __init__(self,token):
        if not token:raise PreparationError('Cadastre o token no environment distribution-bootstrap.')
        self.token=token

    def request(self,method,path,data=None,optional=False):
        if not (path.startswith(BASE+'/') or path.startswith('/users/') or path=='/apps/github-actions'):
            raise PreparationError('Endpoint administrativo não autorizado.')
        body=json.dumps(data).encode() if data is not None else None
        request=urllib.request.Request('https://api.github.com'+path,data=body,method=method,headers={
            'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json',
            'X-GitHub-Api-Version':'2022-11-28','User-Agent':'HUGINN-distribution-preparation'})
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                raw=response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            if optional and error.code==404:return None
            raise PreparationError(f'GitHub recusou {method} {path.split("?")[0]} (HTTP {error.code}). Nenhum segredo foi exibido.') from None
        except (OSError,ValueError):
            raise PreparationError('Falha de rede/resposta administrativa; verifique o estado antes de repetir.') from None

    def items(self,path,key=None):
        result=[]
        for page in range(1,101):
            data=self.request('GET',path+('&' if '?' in path else '?')+f'per_page=100&page={page}')
            values=data[key] if key else data
            result.extend(values)
            if len(values)<100:return result
        raise PreparationError('Listagem administrativa incompleta; operação recusada.')

    def set_secret(self,environment,name,value):
        # Official gh client encrypts to the environment's GitHub public key.
        env=os.environ.copy();env['GH_TOKEN']=self.token
        result=subprocess.run(['gh','secret','set',name,'--repo',REPOSITORY,'--env',environment],
                              input=value,capture_output=True,env=env)
        if result.returncode:raise PreparationError(f'Não foi possível guardar {name} em {environment}; saída suprimida por segurança.')


def reviewers(environment):
    for rule in environment.get('protection_rules',[]):
        if rule['type']=='required_reviewers':
            return [dict(type=r['type'],id=r['reviewer']['id']) for r in rule.get('reviewers',[])],bool(rule.get('prevent_self_review'))
    return [],False


def inspect_environment(api,name):
    environment=api.request('GET',BASE+'/environments/'+name,optional=True)
    if environment and environment.get('deployment_branch_policy',{}):
        policy=environment['deployment_branch_policy']
        if policy.get('custom_branch_policies'):
            policies=api.items(BASE+'/environments/'+name+'/deployment-branch-policies','branch_policies')
            if any(p['name']!='main' or p.get('type','branch')!='branch' for p in policies):
                raise PreparationError(f'{name} contém políticas adicionais. Revise-as em Settings > Environments; não serão removidas automaticamente.')
    return environment


def require_bootstrap_guard(api):
    environment=inspect_environment(api,BOOTSTRAP)
    allowed,prevent=reviewers(environment or {})
    policy=(environment or {}).get('deployment_branch_policy') or {}
    if not allowed or not prevent or not policy.get('custom_branch_policies'):
        raise PreparationError('Proteja distribution-bootstrap com revisor obrigatório, Prevent self-review e somente a branch main antes de executar.')
    policies=api.items(BASE+'/environments/'+BOOTSTRAP+'/deployment-branch-policies','branch_policies')
    if not any(p['name']=='main' and p.get('type','branch')=='branch' for p in policies):
        raise PreparationError('distribution-bootstrap precisa permitir main explicitamente.')


def protect_environment(api,name,existing,reviewer):
    # Existing reviewers and wait times are retained. A new reviewer is not
    # added to an existing list, since doing so could broaden approval authority.
    allowed,_=reviewers(existing or {})
    wait=max([r.get('wait_timer',0) for r in (existing or {}).get('protection_rules',[]) if r['type']=='wait_timer'] or [0])
    api.request('PUT',BASE+'/environments/'+name,dict(wait_timer=wait,prevent_self_review=True,
        reviewers=allowed or [dict(type='User',id=reviewer)],
        deployment_branch_policy=dict(protected_branches=False,custom_branch_policies=True)))
    policies=api.items(BASE+'/environments/'+name+'/deployment-branch-policies','branch_policies')
    if not any(p['name']=='main' and p.get('type','branch')=='branch' for p in policies):
        api.request('POST',BASE+'/environments/'+name+'/deployment-branch-policies',dict(name='main',type='branch'))


def ruleset_payloads(actions_app_id):
    common=dict(enforcement='active',bypass_actors=[])
    return [dict(common,name='HUGINN protected main v1',target='branch',
        conditions=dict(ref_name=dict(include=['refs/heads/main'],exclude=[])),rules=[
            dict(type='deletion'),dict(type='non_fast_forward'),
            dict(type='pull_request',parameters=dict(required_approving_review_count=1,dismiss_stale_reviews_on_push=True,
                 require_code_owner_review=False,require_last_push_approval=True,required_review_thread_resolution=True)),
            dict(type='required_status_checks',parameters=dict(strict_required_status_checks_policy=True,
                 required_status_checks=[dict(context='portable',integration_id=actions_app_id)]))]),
        dict(common,name='HUGINN immutable release tags v1',target='tag',
        conditions=dict(ref_name=dict(include=['refs/tags/v*'],exclude=[])),rules=[dict(type='update'),dict(type='deletion')])]


def contains(actual,expected):
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and contains(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        if not expected:return actual==[]
        return isinstance(actual,list) and all(any(contains(a,e) for a in actual) for e in expected)
    return actual==expected


def add_protections(api):
    app=api.request('GET','/apps/github-actions')
    if app.get('slug')!='github-actions':raise PreparationError('Identidade do provedor de checks inválida.')
    existing=api.items(BASE+'/rulesets')
    ids=[]
    for desired in ruleset_payloads(app['id']):
        canonical=json.dumps(desired,sort_keys=True,separators=(',',':'))
        # Never update/delete unknown existing rules. Add a separate stronger set.
        desired['name']+=' '+hashlib.sha256(canonical.encode()).hexdigest()[:8]
        match=next((r for r in existing if r['name']==desired['name']),None)
        if match:
            detail=api.request('GET',BASE+f'/rulesets/{match["id"]}')
            if not contains(detail,desired):
                raise PreparationError('Ruleset HUGINN foi alterado; revisão manual necessária. Nenhuma regra foi substituída.')
            ids.append(match['id'])
        else:ids.append(api.request('POST',BASE+'/rulesets',desired)['id'])
    return ids


def secret_names(api,environment):
    return {s['name'] for s in api.items(BASE+'/environments/'+environment+'/secrets','secrets')}


def public_mapping(api,ref='main'):
    result=api.request('GET',BASE+'/contents/'+PUBLIC_FILE+'?ref='+urllib.parse.quote(ref,safe=''))
    return json.loads(base64.b64decode(result['content']))


def candidate_pr(api):
    candidates=[p for p in api.items(BASE+'/pulls?state=open&base=main') if p['head']['ref'].startswith('setup/huginn-test-key-')]
    if len(candidates)>1:raise PreparationError('Há múltiplos PRs de chave; revise sem gerar outra chave.')
    return candidates[0] if candidates else None


def publish_public_pr(api,mapping,public,fingerprint):
    main=api.request('GET',BASE+'/git/ref/heads/main')['object']['sha']
    branch='setup/huginn-test-key-'+fingerprint[:12]
    ref=api.request('GET',BASE+'/git/ref/heads/'+branch,optional=True)
    if ref:raise PreparationError('Branch de chave já existe; não será sobrescrita.')
    api.request('POST',BASE+'/git/refs',dict(ref='refs/heads/'+branch,sha=main))
    mapping=dict(mapping);mapping['teste']=public
    api.request('PUT',BASE+'/contents/'+PUBLIC_FILE,dict(message='Prepare test-channel public signing key (no production activation)',
        branch=branch,sha=api.request('GET',BASE+'/contents/'+PUBLIC_FILE+'?ref='+branch)['sha'],
        content=base64.b64encode((json.dumps(mapping,indent=2)+'\n').encode()).decode()))
    return api.request('POST',BASE+'/pulls',dict(title='Review test-channel public signing key — clients remain disabled',
        head=branch,base='main',body=f'''This PR contains ONLY the test public key. Production trust and client activation are unchanged.

Public SHA256 fingerprint: `{fingerprint}`.

Review the bootstrap workflow and its protected `verify-test-key` job before merging. The job must confirm the GitHub environment secret matches this key. No private material is in the PR, artifacts or outputs. A separate reviewer and portable CI approval are required. Do not bypass rules or auto-merge this trust change.'''))


def prepare(api,reviewer_login):
    require_bootstrap_guard(api)
    user=api.request('GET','/users/'+urllib.parse.quote(reviewer_login,safe=''))
    permission=api.request('GET',BASE+'/collaborators/'+urllib.parse.quote(reviewer_login,safe='')+'/permission')['permission']
    if permission not in {'admin','maintain','write'}:raise PreparationError('O revisor deve ser colaborador com permissão write/maintain/admin.')
    test=inspect_environment(api,TEST);recovery=inspect_environment(api,RECOVERY)
    mapping=public_mapping(api)
    names=secret_names(api,TEST) if test else set()
    recovery_names=secret_names(api,RECOVERY) if recovery else set()
    prior=candidate_pr(api)
    if mapping['teste']:
        if SIGNING_SECRET not in names:raise PreparationError('Pública existente sem secret correspondente; restaure a chave original, não gere outra.')
        if RECOVERY_SECRET not in recovery_names:raise PreparationError('Chave existente sem recuperação verificada; não será rotacionada automaticamente.')
        public=mapping['teste'];pr=None
    elif SIGNING_SECRET in names:
        if not prior or RECOVERY_SECRET not in recovery_names:raise PreparationError('Há material de assinatura existente sem cadeia pública/recuperação verificável. Revisão necessária.')
        public=public_mapping(api,prior['head']['ref'])['teste'];pr=prior
    else:
        if prior or recovery_names:raise PreparationError('Preparação parcial existente; preserve o cofre e o PR para recuperação, sem gerar outra chave.')
        public=None;pr=None
    if public is not None:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            Ed25519PublicKey.from_public_bytes(base64.b64decode(public,validate=True))
        except Exception:raise PreparationError('Pública existente/proposta inválida; nenhuma chave será gerada ou substituída.') from None
    ids=add_protections(api)
    protect_environment(api,TEST,test,user['id']);protect_environment(api,RECOVERY,recovery,user['id'])
    if public is None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        key=Ed25519PrivateKey.generate()
        private=base64.b64encode(key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
        public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
        fingerprint=hashlib.sha256(base64.b64decode(public)).hexdigest()
        # Recovery and primary vaults are protected independently. No key files.
        # Never reuse/regenerate/overwrite a key based solely on a secret name.
        api.set_secret(RECOVERY,RECOVERY_SECRET,private)
        api.set_secret(TEST,SIGNING_SECRET,private)
        pr=publish_public_pr(api,mapping,public,fingerprint)
    fingerprint=hashlib.sha256(base64.b64decode(public,validate=True)).hexdigest()
    return dict(public_key=public,fingerprint=fingerprint,pr_url=pr['html_url'] if pr else '',
                pr_sha=pr['head']['sha'] if pr else '',rulesets=ids,production_enabled=False,clients_enabled=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','cleanup']);p.add_argument('--reviewer')
    a=p.parse_args()
    try:
        api=API(os.environ.get('GH_TOKEN'))
        if a.action=='cleanup':
            api.request('DELETE',BASE+'/environments/'+BOOTSTRAP+'/secrets/'+ADMIN_SECRET,optional=True)
            return 0
        if not a.reviewer:raise PreparationError('Informe o login do revisor autorizado.')
        report=prepare(api,a.reviewer)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as out:
                for key in ['public_key','fingerprint','pr_url','pr_sha']:out.write(f'{key}={report[key]}\n')
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:
                out.write('## Canal de testes preparado, sem ativação\n\n')
                out.write(f"Fingerprint público: `{report['fingerprint']}`\n\nPR para revisão: {report['pr_url'] or 'pública já revisada'}\n\n")
                out.write('Aguarde verify-test-key e revisão independente do PR. Produção e clientes permanecem desativados.\n')
        print('Preparação concluída; somente metadados públicos foram emitidos.')
        return 0
    except PreparationError as error:print(str(error));return 1
    except Exception:print('Preparação interrompida. Verifique o estado dos cofres/PR antes de repetir; detalhes suprimidos para proteger segredos.');return 1


if __name__=='__main__':raise SystemExit(main())
