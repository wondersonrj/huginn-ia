"""CI-only failed worker ZIP; never uploaded or published."""
import argparse
from pathlib import Path
import zipfile

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path); parser.add_argument('destination', type=Path)
    args = parser.parse_args(); args.destination.parent.mkdir(parents=True, exist_ok=True)
    changed = 0
    with zipfile.ZipFile(args.source) as source, zipfile.ZipFile(args.destination, 'w', zipfile.ZIP_DEFLATED) as target:
        for member in source.infolist():
            data = source.read(member)
            if member.filename.endswith('/server.py'):
                data = b'raise SystemExit(42)\n'; changed += 1
            target.writestr(member, data)
    assert changed == 1
