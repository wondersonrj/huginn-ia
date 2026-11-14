import base64
import copy
import json
from pathlib import Path
import sys
from urllib.parse import unquote
from unittest.mock import patch

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/distribution'))
import prepare_test_channel as prep
import verify_test_key


def protected():
    return dict(protection_rules=[dict(type='required_reviewers',prevent_self_review=False,reviewers=[dict(type='User',reviewer=dict(id=12))])],deployment_branch_policy=dict(custom_branch_policies=True,protected_branches=False))


class FakeAPI:
    def __init__(self):
        self.environments={prep.BOOTSTRAP:protected()}
        self.policies={prep.BOOTSTRAP:[dict(name='main',type='branch')]}
        self.secrets={};self.writes=[];self.private=[];self.rules=[];self.pulls=[]
        self.mapping=dict(teste='',estavel='PRODUCTION-PUBLIC-UNCHANGED')
        self.branch_mapping={};self.calls=[]
    def request(self,method,path,data=None,optional=False):
        self.calls.append((method,path,copy.deepcopy(data)))
        if path=='/apps/github-actions':return dict(id=15368,slug='github-actions')
        if path.startswith('/users/') or path=='/user':return dict(id=12)
        if '/collaborators/' in path:return dict(permission='admin')
        if path==prep.BASE+'/git/ref/heads/main':return dict(object=dict(sha='a'*40))
        if path.startswith(prep.BASE+'/git/ref/heads/setup/'):return None
        if path==prep.BASE+'/git/refs':return {}
        if path.startswith(prep.BASE+'/contents/'):
            if method=='PUT':
                self.branch_mapping[data['branch']]=json.loads(base64.b64decode(data['content']));return {}
            ref=unquote(path.partition('?ref=')[2]) or 'main'
            mapping=self.branch_mapping.get(ref,self.mapping)
            return dict(content=base64.b64encode(json.dumps(mapping).encode()).decode(),sha='file-sha')
        if path==prep.BASE+'/pulls' and method=='POST':
            result=dict(html_url='https://github.com/wondersonrj/huginn-ia/pull/99',head=dict(ref=data['head'],sha='b'*40))
            self.pulls.append(result);return result
        if path==prep.BASE+'/rulesets' and method=='POST':
            value=copy.deepcopy(data)|dict(id=len(self.rules)+1);self.rules.append(value);return value
        if '/rulesets/' in path:
            value=next(r for r in self.rules if str(r['id'])==path.rsplit('/',1)[-1])
            if method=='PUT':value.update(copy.deepcopy(data))
            return value
        if '/environments/' in path:
            tail=path.split('/environments/')[1];name=tail.split('/')[0]
            if tail.endswith('/deployment-branch-policies'):
                self.policies.setdefault(name,[]).append(data);return data
            if '/secrets/' in tail and method=='DELETE':return None
            if method=='GET':return self.environments.get(name)
            if method=='PUT':
                self.environments[name]=dict(protection_rules=[dict(type='required_reviewers',prevent_self_review=data['prevent_self_review'],reviewers=[dict(type=r['type'],reviewer=dict(id=r['id'])) for r in data['reviewers']]),dict(type='wait_timer',wait_timer=data['wait_timer'])],deployment_branch_policy=data['deployment_branch_policy'])
                return self.environments[name]
        raise AssertionError((method,path))
    def items(self,path,key=None):
        if path.startswith(prep.BASE+'/rulesets'):return self.rules
        if path.startswith(prep.BASE+'/pulls'):return self.pulls
        name=path.split('/environments/')[1].split('/')[0]
        if path.endswith('/secrets'):return [dict(name=n) for n in self.secrets.get(name,set())]
        return self.policies.get(name,[])
    def set_secret(self,environment,name,value):
        self.writes.append((environment,name));self.private.append(value)
        self.secrets.setdefault(environment,set()).add(name)


def test_new_test_key_is_only_in_protected_vaults_and_public_pr():
    api=FakeAPI();report=prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert set(api.writes)=={(prep.TEST,prep.SIGNING_SECRET),(prep.RECOVERY,prep.RECOVERY_SECRET)}
    assert len(api.private)==2 and api.private[0]==api.private[1]
    assert not report['production_enabled'] and not report['clients_enabled']
    mapping=next(iter(api.branch_mapping.values()))
    assert mapping['estavel']=='PRODUCTION-PUBLIC-UNCHANGED'
    assert mapping['teste']==report['public_key']
    assert api.private[0].decode() not in json.dumps(report)
    assert all(not p.startswith(prep.BASE+'/environments/windows-release-estavel') for _,p,_ in api.calls)
    assert not any(m in {'PATCH','DELETE'} and '/rulesets/' in p for m,p,_ in api.calls)


def test_rerun_never_rotates_or_overwrites_secrets():
    api=FakeAPI();first=prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION);writes=len(api.private)
    second=prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert first['public_key']==second['public_key']
    assert len(api.private)==writes and len(api.rules)==2


def test_single_admin_environment_keeps_wait_time_and_manual_gate():
    api=FakeAPI();api.environments[prep.TEST]=protected()
    api.environments[prep.TEST]['protection_rules'][0].update(prevent_self_review=True,reviewers=[dict(type='User',reviewer=dict(id=9))])
    api.environments[prep.TEST]['protection_rules'].append(dict(type='wait_timer',wait_timer=20))
    api.policies[prep.TEST]=[dict(name='main',type='branch')]
    prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    allowed,prevent=prep.reviewers(api.environments[prep.TEST])
    assert allowed==[dict(type='User',id=12)] and not prevent
    assert any(r.get('wait_timer')==20 for r in api.environments[prep.TEST]['protection_rules'])


def test_unprotected_admin_environment_fails_before_mutation():
    api=FakeAPI();api.environments[prep.BOOTSTRAP]['protection_rules']=[]
    with pytest.raises(prep.PreparationError,match='Configure distribution-bootstrap'):prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert not any(m!='GET' for m,_,_ in api.calls) and not api.private


def test_existing_unknown_secret_is_never_replaced():
    api=FakeAPI();api.environments[prep.TEST]=protected();api.policies[prep.TEST]=[dict(name='main',type='branch')]
    api.secrets[prep.TEST]={prep.SIGNING_SECRET}
    with pytest.raises(prep.PreparationError,match='existente'):prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert not api.private


def test_extra_branch_access_is_not_silently_changed():
    api=FakeAPI();api.environments[prep.TEST]=protected();api.policies[prep.TEST]=[dict(name='*',type='branch')]
    with pytest.raises(prep.PreparationError,match='políticas adicionais'):prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert not any(m!='GET' for m,_,_ in api.calls)


def test_rule_comparison_never_accepts_bypass_or_exclusions():
    desired=prep.ruleset_payloads(15368)[0]
    actual=copy.deepcopy(desired);actual['server_metadata']='ignored'
    assert prep.contains(actual,desired)
    actual['bypass_actors']=[dict(actor_type='RepositoryRole',actor_id=5,bypass_mode='always')]
    assert not prep.contains(actual,desired)
    actual=copy.deepcopy(desired);actual['conditions']['ref_name']['exclude']=['main']
    assert not prep.contains(actual,desired)


def test_vault_proof_reports_failure_without_secrets(tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('HUGINN_RELEASE_SIGNING_KEY','invalid-test-placeholder')
    monkeypatch.setenv('EXPECTED_PUBLIC_KEY','invalid-test-placeholder')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(tmp_path/'summary'))
    with patch('verify_test_key.post_status') as status:
        assert verify_test_key.main()==1
        status.assert_called_once_with('failure')
    assert 'invalid-test-placeholder' not in capsys.readouterr().out


def test_vault_proof_verifies_private_without_exposing_it(tmp_path,monkeypatch,capsys):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    key=Ed25519PrivateKey.generate()
    raw=base64.b64encode(key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())).decode()
    public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    monkeypatch.setenv('HUGINN_RELEASE_SIGNING_KEY',raw)
    monkeypatch.setenv('EXPECTED_PUBLIC_KEY',public)
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(tmp_path/'summary'))
    with patch('verify_test_key.post_status') as status:
        assert verify_test_key.main()==0
        status.assert_called_once_with('success')
    assert raw not in capsys.readouterr().out and raw not in (tmp_path/'summary').read_text()


def test_altered_named_ruleset_is_not_replaced():
    api=FakeAPI();prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    api.rules[0]['bypass_actors']=[dict(actor_type='RepositoryRole',actor_id=5,bypass_mode='always')]
    writes=len(api.private)
    with pytest.raises(prep.PreparationError,match='Ruleset'):prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert len(api.private)==writes
    assert not any(m=='PUT' and '/rulesets/' in p for m,p,_ in api.calls)


def test_admin_credentials_are_never_forwarded_on_redirect():
    handler=prep.NoRedirect()
    request=prep.urllib.request.Request('https://api.github.com/repos/wondersonrj/huginn-ia/environments/distribution-bootstrap',headers={'Authorization':'Bearer test-only-not-a-real-token'})
    with pytest.raises(prep.PreparationError,match='Redirecionamento'):
        handler.redirect_request(request,None,302,'Found',{},'https://untrusted.example/')


@pytest.mark.parametrize('admin,confirmation',[('other-user',prep.CONFIRMATION),(prep.ADMINISTRATOR,''),(prep.ADMINISTRATOR,'yes')])
def test_single_admin_confirmation_required_before_any_api_call(admin,confirmation):
    api=FakeAPI()
    with pytest.raises(prep.PreparationError,match='confirmação'):
        prep.prepare(api,admin,confirmation)
    assert not api.calls and not api.private


def test_other_token_owner_cannot_prepare_distribution():
    api=FakeAPI();request=api.request
    def other(method,path,*args,**kwargs):
        if path=='/user':return dict(id=99)
        return request(method,path,*args,**kwargs)
    api.request=other
    with pytest.raises(prep.PreparationError,match='token'):
        prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert not api.private


def test_single_admin_branch_policy_keeps_pr_checks_and_immutable_tags():
    branch,tags=prep.ruleset_payloads(15368)
    pull=next(r for r in branch['rules'] if r['type']=='pull_request')['parameters']
    assert pull['required_approving_review_count']==0 and pull['require_last_push_approval'] is False
    assert {'deletion','non_fast_forward','pull_request','required_status_checks'}=={r['type'] for r in branch['rules']}
    assert branch['bypass_actors']==[] and tags['bypass_actors']==[]
    assert {r['type'] for r in tags['rules']}=={'update','deletion'}


def test_known_legacy_rule_migration_keeps_all_other_protections():
    api=FakeAPI()
    old=prep.named(prep.ruleset_payloads(15368,legacy=True)[0]);old['id']=7
    old['rules'].append(dict(type='required_linear_history'))
    api.rules.append(old)
    prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    migrated=next(r for r in api.rules if r['id']==7)
    parameters=next(r for r in migrated['rules'] if r['type']=='pull_request')['parameters']
    assert parameters['required_approving_review_count']==0 and not parameters['require_last_push_approval']
    assert dict(type='required_linear_history') in migrated['rules']
    assert migrated['conditions']==old['conditions'] and migrated['bypass_actors']==[]
    updates=len([1 for m,p,d in api.calls if m=='PUT' and '/rulesets/' in p])
    prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert len([1 for m,p,d in api.calls if m=='PUT' and '/rulesets/' in p])==updates


def test_customized_legacy_reviewer_rule_requires_manual_migration():
    api=FakeAPI()
    old=prep.named(prep.ruleset_payloads(15368,legacy=True)[0]);old['id']=7
    next(r for r in old['rules'] if r['type']=='pull_request')['parameters']['required_approving_review_count']=2
    api.rules.append(old)
    with pytest.raises(prep.PreparationError,match='personalizada'):
        prep.prepare(api,prep.ADMINISTRATOR,prep.CONFIRMATION)
    assert not any(m=='PUT' and '/rulesets/' in p for m,p,_ in api.calls)
    assert not api.private


def test_bootstrap_does_not_require_a_second_person():
    api=FakeAPI()
    prep.require_bootstrap_guard(api,12)
    api.environments[prep.BOOTSTRAP]['protection_rules'][0]['prevent_self_review']=True
    with pytest.raises(prep.PreparationError,match='Prevent self-review'):
        prep.require_bootstrap_guard(api,12)


def test_test_release_requires_own_administrator_confirmation_before_api(monkeypatch):
    import prepare_test_release
    monkeypatch.setenv('GITHUB_ACTOR','wondersonrj')
    monkeypatch.setenv('GITHUB_REPOSITORY',prep.REPOSITORY)
    monkeypatch.setenv('GITHUB_REF','refs/heads/main')
    monkeypatch.delenv('CONFIRM_TEST_RELEASE',raising=False)
    with patch.object(sys,'argv',['prepare_test_release.py','--version','0.3.0']),patch('prepare_test_release.api') as api:
        assert prepare_test_release.main()==1
        api.assert_not_called()


def test_test_release_cannot_be_dispatched_by_another_actor(monkeypatch):
    import prepare_test_release
    monkeypatch.setenv('GITHUB_ACTOR','other-user')
    monkeypatch.setenv('GITHUB_REPOSITORY',prep.REPOSITORY)
    monkeypatch.setenv('GITHUB_REF','refs/heads/main')
    monkeypatch.setenv('CONFIRM_TEST_RELEASE','true')
    with patch.object(sys,'argv',['prepare_test_release.py','--version','0.3.0']),patch('prepare_test_release.api') as api:
        assert prepare_test_release.main()==1
        api.assert_not_called()


@pytest.mark.parametrize('condition,message', [
    ('reviewer', 'Required reviewers'),
    ('self_review', 'Prevent self-review'),
    ('branch_mode', 'Selected branches and tags'),
    ('missing_main', 'main explicitamente'),
    ('extra_branch', 'políticas adicionais'),
    ('main_tag', 'políticas adicionais'),
])
def test_bootstrap_reports_exact_failed_guard_without_mutations(condition,message):
    api=FakeAPI()
    environment=api.environments[prep.BOOTSTRAP]
    if condition=='reviewer':
        environment['protection_rules'][0]['reviewers']=[]
    elif condition=='self_review':
        environment['protection_rules'][0]['prevent_self_review']=True
    elif condition=='branch_mode':
        environment['deployment_branch_policy']=dict(protected_branches=True,custom_branch_policies=False)
    elif condition=='missing_main':
        api.policies[prep.BOOTSTRAP]=[]
    elif condition=='extra_branch':
        api.policies[prep.BOOTSTRAP].append(dict(name='*',type='branch'))
    elif condition=='main_tag':
        api.policies[prep.BOOTSTRAP]=[dict(name='main',type='tag')]
    with pytest.raises(prep.PreparationError,match=message):
        prep.require_bootstrap_guard(api,12)
    assert all(method=='GET' for method,_,_ in api.calls)
    assert not api.private


@pytest.mark.parametrize('status,optional_result',[(403,False),(404,True)])
def test_cleanup_does_not_treat_forbidden_as_success(status,optional_result):
    import urllib.error
    from unittest.mock import MagicMock
    opener=MagicMock()
    opener.open.side_effect=urllib.error.HTTPError('https://api.github.com',status,'failure',{},None)
    with patch.object(prep.urllib.request,'build_opener',return_value=opener):
        api=prep.API('test-placeholder')
        path=prep.BASE+'/environments/'+prep.BOOTSTRAP+'/secrets/'+prep.ADMIN_SECRET
        if optional_result:
            assert api.request('DELETE',path,optional=True) is None
        else:
            with pytest.raises(prep.PreparationError,match='HTTP 403'):
                api.request('DELETE',path,optional=True)
