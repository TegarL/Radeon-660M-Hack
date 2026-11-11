#!/usr/bin/env python3
"""Check candidate 23 source identity and run the existing VCN remapper test.

An optional generated header is checked against the local-generation hash.
These checks do not load a driver or test video decoding on hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated-header', type=Path, help='locally generated command_staging.hpp')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'source-lock.json').read_text())
    expected = lock['source']['files']
    actual = {p.relative_to(ROOT).as_posix(): digest(p)
              for p in sorted((ROOT / 'src/RembrandtGfx').iterdir()) if p.is_file()}
    if actual != expected:
        changed = sorted(k for k in set(expected) | set(actual) if expected.get(k) != actual.get(k))
        raise ValueError('Source differs from the exported candidate 23 snapshot: ' + ', '.join(changed))
    print(f'PASS: {len(expected)} exported source files match source-lock.json')
    if args.generated_header:
        if digest(args.generated_header) != lock['command_staging']['generated_header_sha256']:
            raise ValueError('Generated command staging header differs from candidate 23')
        print('PASS: complete generated header matches candidate 23')
    build = ROOT / 'build/tests'
    build.mkdir(parents=True, exist_ok=True)
    executable = build / 'test-vcn-vm'
    subprocess.run(['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(ROOT / 'src/RembrandtGfx/test_vcn_vm.cpp'),
                    '-o', str(executable)], check=True)
    subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
