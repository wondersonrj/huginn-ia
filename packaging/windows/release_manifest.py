"""Sign a release manifest. Private key comes ONLY from Actions environment."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from updater import REPO, version_tuple
from signing_keys import public_key
import zipfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--version', required=True)
    p.add_argument('--channel', choices=['teste', 'estavel'], required=True)
    p.add_argument('--notes', type=Path, required=True)
    p.add_argument('--zip', type=Path, default=Path('release/HUGINN-IA-Windows-x64.zip'))
    p.add_argument('--public-key-file', type=Path)
    args = p.parse_args()
    version_tuple(args.version)
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(os.environ['HUGINN_RELEASE_SIGNING_KEY'], validate=True))
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    expected = public_key(args.channel, args.public_key_file)
    if public != expected:
        raise SystemExit('Chave de assinatura não corresponde à chave pública revisada.')
    runtime_id = hashlib.sha256(Path('packaging/windows/requirements.lock').read_bytes()).hexdigest()
    with zipfile.ZipFile(args.zip) as bundle:
        cfg=json.loads(bundle.read('HUGINN-IA-Windows-x64/bootstrap.json'))
        if (cfg['version'],cfg['channel'],cfg['runtime_id'],cfg['public_key']) != (args.version,args.channel,runtime_id,expected):
            raise SystemExit('Identidade do pacote não corresponde à release/chave selecionada.')
    signed = dict(version=args.version, channel=args.channel,
                  url=f'https://github.com/{REPO}/releases/download/v{args.version}/HUGINN-IA-Windows-x64.zip',
                  sha256=hashlib.sha256(args.zip.read_bytes()).hexdigest(),
                  notes=args.notes.read_text(encoding='utf-8')[:8000], bootstrap_version=1,
                  runtime_id=runtime_id)
    canonical = json.dumps(signed, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    envelope = dict(signed=signed, signature=base64.b64encode(key.sign(canonical)).decode())
    args.zip.with_name('manifest.json').write_text(json.dumps(envelope, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
