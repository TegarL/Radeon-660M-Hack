#!/usr/bin/env python3
"""Download the exact recorded AMD firmware from the pinned linux-firmware commit.

Files stay in build/private/amdgpu by default. No firmware
is installed or added to the public source tree.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def fetch(output, item):
    name, spec = item
    path = output / name
    if path.exists():
        data = path.read_bytes()
    else:
        with urllib.request.urlopen(spec['source_url'], timeout=60) as response:
            data = response.read()
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != spec['bytes'] or actual != spec['sha256']:
        raise ValueError(f'{name} does not match source-lock.json; no replacement was written')
    if not path.exists():
        path.write_bytes(data)
    return {'file': name, 'bytes': len(data), 'sha256': actual, 'source_url': spec['source_url']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/private/amdgpu')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / 'source-lock.json').read_text())['firmware']
    files = list(lock['files'].items())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda item: fetch(output, item), files))
    manifest = {'source_commit': lock['source']['commit'], 'files': records}
    (output / 'download-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Checked {len(lock["files"])} raw firmware files')
    print(f'Source commit: {lock["source"]["commit"]}')
    print(f'Output: {output}')


if __name__ == '__main__':
    main()
