"""CI-only failed worker ZIP; never uploaded or published."""
import argparse
import json
from pathlib import Path
import zipfile


def make(source_path, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    changed = 0
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as target:
        version = json.loads(source.read('HUGINN-IA-Windows-x64/bootstrap.json'))['version']
        entrypoint = f'HUGINN-IA-Windows-x64/versions/{version}/server.py'
        for member in source.infolist():
            data = source.read(member)
            if member.filename == entrypoint:
                data = b'raise SystemExit(42)\n'; changed += 1
            target.writestr(member, data)
    assert changed == 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path); parser.add_argument('destination', type=Path)
    args = parser.parse_args(); make(args.source, args.destination)
