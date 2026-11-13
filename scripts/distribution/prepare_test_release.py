"""Create an immutable test tag from tested main and dispatch disabled release."""
import argparse
import base64
import json
import os
import subprocess
import sys
import time

REPO='wondersonrj/huginn-ia'


def api(method,path,data=None):
    command=['gh','api','--method',method,f'repos/{REPO}/'+path]
    if data is not None:command+=['--input','-']
    result=subprocess.run(command,input=json.dumps(data).encode() if data is not None else None,capture_output=True)
    if result.returncode:raise RuntimeError('Operação GitHub recusada; nenhum segredo foi exibido.')
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    sys.path.insert(0,os.path.join(os.path.dirname(__file__),'../../packaging/windows'))
    from updater import version_tuple
    p=argparse.ArgumentParser();p.add_argument('--version',required=True);a=p.parse_args()
    try:
        version_tuple(a.version)
        sha=os.environ['GITHUB_SHA']
        mapping=json.loads(base64.b64decode(api('GET','contents/packaging/windows/release-public-keys.json?ref='+sha)['content']))
        if not mapping['teste']:raise RuntimeError('Primeiro revise e mescle o PR da chave pública de testes.')
        current=json.loads(base64.b64decode(api('GET','contents/packaging/windows/version.json?ref='+sha)['content']))
        if version_tuple(a.version)<=version_tuple(current['version']):raise RuntimeError('Escolha versão maior que a versão do bootstrap atual.')
        # Wait for the known asynchronous CI for this exact protected main commit.
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            runs=api('GET',f'actions/workflows/windows-portable.yml/runs?head_sha={sha}&event=push&branch=main&per_page=30')['workflow_runs']
            if any(r['conclusion']=='success' for r in runs):break
            if runs and all(r['status']=='completed' for r in runs):raise RuntimeError('CI de main não foi aprovado. Corrija antes de criar a tag.')
            time.sleep(10)
        else:raise RuntimeError('CI ainda não confirmou main; nenhuma tag foi criada.')
        api('POST','git/refs',dict(ref='refs/tags/v'+a.version,sha=sha))
        api('POST','actions/workflows/windows-portable.yml/dispatches',dict(ref='main',inputs=dict(
            release_tag='v'+a.version,approve_release=True,enable_client_updates=False,channel='teste')))
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:
            out.write(f'## Release de teste solicitada\n\nTag: `v{a.version}` no commit `{sha}`. Canal `teste`; atualizador de novos bootstraps DESATIVADO.\n\nAbra Actions → Windows portable build e aprove windows-release-teste após conferir os testes. Nenhuma instalação existente foi alterada.\n')
        print('Tag de teste criada; publicação aguarda testes e aprovação do environment.')
        return 0
    except Exception as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Preparação recusada. Confira versão, tag e CI.');return 1


if __name__=='__main__':raise SystemExit(main())
