"""Attest that protected environment secret matches the proposed PUBLIC key."""
import base64
import hashlib
import json
import os
import re
import urllib.request
from prepare_test_channel import NoRedirect
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def post_status(state):
    sha=os.environ.get('PUBLIC_PR_SHA','')
    if not sha:return
    if not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('invalid commit')
    context=os.environ.get('STATUS_CONTEXT','test-signing-vault')
    if context not in {'test-signing-vault','test-signing-recovery'}:raise ValueError('invalid context')
    data=json.dumps(dict(state=state,context=context,
        description='Protected vault/public-key verification: '+state,
        target_url='https://github.com/wondersonrj/huginn-ia/actions/runs/'+os.environ['GITHUB_RUN_ID'])).encode()
    request=urllib.request.Request('https://api.github.com/repos/wondersonrj/huginn-ia/statuses/'+sha,data=data,method='POST',headers={
        'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'HUGINN-vault-verification'})
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=30):pass


def main():
    try:
        raw=base64.b64decode(os.environ['HUGINN_RELEASE_SIGNING_KEY'],validate=True)
        expected=base64.b64decode(os.environ['EXPECTED_PUBLIC_KEY'],validate=True)
        key=Ed25519PrivateKey.from_private_bytes(raw)
        actual=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        if actual!=expected:raise ValueError('trust mismatch')
        challenge=('HUGINN test vault verification '+os.environ.get('GITHUB_RUN_ID','local')).encode()
        key.public_key().verify(key.sign(challenge),challenge)
        fingerprint=hashlib.sha256(actual).hexdigest()
        post_status('success')
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as out:
            out.write(f'## Cofre verificado\n\nFingerprint público: `{fingerprint}`.\n\nAssinatura/verificação local aprovada; produção e clientes não foram ativados. Revise o PR público antes de mesclar.\n')
        print('Cofre e chave pública de testes correspondem; nenhum segredo foi emitido.')
        return 0
    except Exception:
        try:post_status('failure')
        except Exception:pass
        print('Verificação do cofre falhou; não mescle a chave nem ative o canal. Detalhes suprimidos para proteger segredos.')
        return 1


if __name__=='__main__':raise SystemExit(main())
