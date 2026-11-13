"""Use an actual published signed release and Windows package, not mock ZIPs.
Uses two TEMPORARY installations; never mutates a user's installed bootstrap.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from launcher import Supervisor
from updater import API, UpdateError, atomic_json, discover, fetch


def run(baseline, expected, output, python=None):
    proofs=[]
    # Authenticated catalog retrieval in CI only; never send token to asset hosts.
    raw_catalog=subprocess.run(['gh','api',f'repos/wondersonrj/huginn-ia/releases?per_page=30'],
                            capture_output=True,check=True).stdout
    # Isolate the validation tag from unrelated real production trust anchors.
    catalog=json.dumps([r for r in json.loads(raw_catalog) if r.get('tag_name')=='v'+expected]).encode()
    os.environ.pop('GH_TOKEN',None)  # Never pass the CI publishing token to the application child.
    def published(url,limit=100*1024*1024):
        return catalog if url==API else fetch(url,limit)
    for rollback in [True,False]:
        with tempfile.TemporaryDirectory(prefix='HUGINN real release isolated ') as temp:
            with zipfile.ZipFile(baseline) as bundle:
                bundle.extractall(temp)
            root=Path(temp)/'HUGINN-IA-Windows-x64'
            original=(root/'bootstrap.json').read_bytes()
            cfg=json.loads(original)
            assert cfg['updates_enabled'] is False
            cfg['updates_enabled']=True  # ONLY in-memory approval in this isolated CI process.
            supervisor=Supervisor(root,cfg,python)
            engine=supervisor.updater
            atomic_json(engine.state/'current.json',{'version':cfg['version']})
            (engine.state/'preferences.json').write_text('{"theme":"dark"}')
            try:
                supervisor.start(cfg['version'])
                envelope=discover(cfg,cfg['version'],download=published)
                assert envelope and envelope['signed']['version']==expected
                def start(version):
                    supervisor.start(version)
                    if rollback and version==expected:
                        raise UpdateError('CI: deliberate failed readiness confirmation')
                try:
                    # Default downloader: actual HTTPS asset from the published release.
                    engine.apply(envelope,supervisor.stop,start,lambda data:True)
                    assert not rollback
                except UpdateError as error:
                    assert rollback and 'anterior restaurada' in str(error)
                actual=cfg['version'] if rollback else expected
                assert engine.current()==actual
                assert supervisor.process.poll() is None
                assert (root/'bootstrap.json').read_bytes()==original
                assert json.loads((engine.state/'preferences.json').read_text())=={'theme':'dark'}
                proofs.append(dict(mode='rollback' if rollback else 'upgrade',from_version=cfg['version'],
                                   expected_version=actual,confirmed_version=engine.current(),
                                   release_url=envelope['signed']['url'],sha256=envelope['signed']['sha256'],
                                   bootstrap_unchanged=True,preferences_preserved=True))
                print(f'::notice title=Real GitHub update::{sys.platform} {proofs[-1]["mode"]}: {cfg["version"]} -> {actual}',flush=True)
            finally:
                supervisor.stop()
                if supervisor.socket is not None:supervisor.socket.close()
    output.write_text(json.dumps(dict(platform=sys.platform,real_https_release=True,
        client_updates_enabled=False,oracle_accessed=False,expected_release_only=True,proofs=proofs),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--expected',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--python',type=Path)
    a=p.parse_args()
    try:
        run(a.baseline,a.expected,a.output,a.python.absolute() if a.python else None)
    except Exception as error:
        print(f'::error title=Real release validation::{type(error).__name__}: validation did not complete',flush=True)
        raise
