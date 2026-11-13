"""Ephemeral CI-only trust anchor. Never touches production keys or clients."""
import argparse
import base64
import os
from pathlib import Path
import subprocess
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from signing_keys import secure_directory


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['create','sign','destroy'])
    p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--version')
    p.add_argument('--zip',type=Path)
    a=p.parse_args()
    private=a.directory/'ephemeral.private.raw'
    if a.action=='create':
        directory=secure_directory(a.directory)
        key=Ed25519PrivateKey.generate()
        with private.open('xb') as stream:
            stream.write(key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
        private.chmod(0o600)
        public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
        (directory/'ephemeral.pub').write_text(public,encoding='ascii')
    elif a.action=='sign':
        env=os.environ.copy()
        env['HUGINN_RELEASE_SIGNING_KEY']=base64.b64encode(private.read_bytes()).decode()
        subprocess.run([sys.executable,str(Path(__file__).with_name('release_manifest.py')),
                        '--version',a.version,'--channel','teste','--zip',str(a.zip),
                        '--notes','packaging/windows/VALIDATION-RELEASE-NOTES.md',
                        '--public-key-file',str(a.directory/'ephemeral.pub')],env=env,check=True)
    else:
        private.unlink(missing_ok=True)


if __name__=='__main__':
    main()
