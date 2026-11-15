"""Installer's local health activation/rollback and explicit current-user data removal.
No network distribution, release activation, forced process termination or Oracle calls.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def activate(root):
    from launcher import Supervisor
    from updater import atomic_json, exclusive_lock
    root = Path(root)
    config = json.loads((root / 'bootstrap.json').read_text())
    state = root / 'state'; state.mkdir(exist_ok=True)
    pointer = state / 'current.json'
    previous = json.loads(pointer.read_text()) if pointer.exists() else None
    with exclusive_lock(state / 'supervisor.lock'):
        supervisor = Supervisor(root, config)
        # Use a managed free port for the health probe, without touching another service.
        import socket
        supervisor.socket = socket.socket(); supervisor.socket.bind(('127.0.0.1', 0)); supervisor.socket.listen(128)
        try:
            supervisor.start(config['version'])
            atomic_json(pointer, {'version': config['version']})
            if previous:
                atomic_json(state / 'installer-backup.json', previous)
        except Exception:
            if previous:
                atomic_json(pointer, previous)
            raise
        finally:
            supervisor.stop()
            supervisor.socket.close()


def remove_data(root):
    from desktop import backend_path
    root = Path(root)
    config = json.loads((root / 'bootstrap.json').read_text())
    backend_path(root, config['version'])
    from app.connection_store import current_store, safe_path
    os.environ['HUGINN_STATE_DIR'] = str(root / 'state')
    store = current_store()
    if store is None:
        raise RuntimeError('Windows user vault required')
    safe_path(store.root)
    if store.root.exists():
        # Exact computed user/installation directory only; never request-supplied paths.
        shutil.rmtree(store.root)
    # Keep/remove decision includes only this installation's updater preferences/state.
    state = root / 'state'
    safe_path(state)
    if state.exists():
        shutil.rmtree(state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--activate', action='store_true')
    group.add_argument('--remove-data', action='store_true')
    args = parser.parse_args()
    try:
        activate(ROOT) if args.activate else remove_data(ROOT)
    except Exception:
        # No exception text/traceback can expose a credential or local DSN.
        print('HUGINN: operacao local de instalacao recusada; dados/servicos externos nao foram alterados.')
        raise SystemExit(1)
