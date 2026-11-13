"""Offline key custody and secure stdin upload. Never prints a private key."""
import argparse
import base64
import csv
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

REPO = Path(__file__).resolve().parents[2]


def public_key(channel, override=None):
    value = (Path(override).read_text().strip() if override else
             json.loads((REPO/'packaging/windows/release-public-keys.json').read_text())[channel])
    if value:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(value,validate=True))
    return value


def secure_directory(path):
    path = Path(path).resolve()
    if path.is_relative_to(REPO):
        raise ValueError('Chaves privadas devem ficar fora do repositório.')
    path.mkdir(mode=0o700,parents=True,exist_ok=False)
    if os.name == 'nt':
        identity = subprocess.run(['whoami.exe','/user','/fo','csv','/nh'],capture_output=True,text=True,check=True)
        sid = next(row[1].strip() for row in csv.reader(io.StringIO(identity.stdout)) if len(row)>1 and row[1].strip().startswith('S-1-'))
        subprocess.run(['icacls.exe',str(path),'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)F',
                        '/grant:r','*S-1-5-18:(OI)(CI)F'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return path


def generate(directory, channel, password):
    if len(password) < 16:
        raise ValueError('Use uma frase-senha exclusiva com pelo menos 16 caracteres.')
    directory = secure_directory(directory)
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
                                serialization.BestAvailableEncryption(password.encode()))
    private_path = directory/f'{channel}.private.pem'
    with private_path.open('xb') as stream:
        stream.write(private)
    private_path.chmod(0o600)
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    (directory/f'{channel}.pub').write_text(public+'\n',encoding='ascii')
    return private_path, hashlib.sha256(base64.b64decode(public)).hexdigest()


def upload(private_path, channel, password):
    if Path(private_path).resolve().is_relative_to(REPO):
        raise ValueError('Mova a chave privada para fora do repositório antes do upload.')
    key = serialization.load_pem_private_key(Path(private_path).read_bytes(),password=password.encode())
    if not isinstance(key,Ed25519PrivateKey):
        raise ValueError('Tipo de chave incorreto.')
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    if public != public_key(channel):
        raise ValueError('A chave pública deve ser revisada e cadastrada no canal antes do upload.')
    raw = base64.b64encode(key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
    # Never place key material in argv, stdout, temporary plaintext files or shell commands.
    result = subprocess.run(['gh','secret','set','HUGINN_RELEASE_SIGNING_KEY','--repo','wondersonrj/huginn-ia',
                             '--env',f'windows-release-{channel}'],input=raw,capture_output=True)
    if result.returncode:
        raise RuntimeError('Upload recusado. Verifique autenticação, environment e permissão administrativa do gh.')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['generate','upload','import-public'])
    p.add_argument('--channel',choices=['teste','estavel'],required=True)
    p.add_argument('--path',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.action=='generate':
            password=getpass.getpass('Frase-senha (não será salva): ')
            if password!=getpass.getpass('Repita a frase-senha: '):
                raise ValueError('Frases-senha diferentes.')
            private,fingerprint=generate(a.path,a.channel,password)
            print(f'Chave privada criptografada criada fora do repositório: {private}')
            print(f'Fingerprint público SHA256: {fingerprint}')
        elif a.action=='import-public':
            value=public_key(a.channel,a.path)
            if not value:raise ValueError('Chave pública vazia.')
            target=REPO/'packaging/windows/release-public-keys.json'
            mapping=json.loads(target.read_text());mapping[a.channel]=value
            target.write_text(json.dumps(mapping,indent=2)+'\n')
            print('Somente a chave pública foi importada. Revise a alteração antes do commit.')
        else:
            upload(a.path,a.channel,getpass.getpass('Frase-senha: '))
            print('Secret enviado ao environment do canal; nenhum valor foi registrado.')
    except Exception as error:
        # No traceback may expose key bytes or secret subprocess input.
        print(str(error) if isinstance(error,(ValueError,RuntimeError)) else 'Operação recusada; verifique chave, frase-senha e permissões.',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
