#!/usr/bin/env python3
"""Build the exported candidate 23 source as an x86_64 RembrandtGfx kext.

Requires macOS Command Line Tools, Python 3, local yellow_carp firmware and the
matching Tahoe 25G332 Metal function. Compressed firmware also requires zstd.
Dependencies are downloaded at the commits and archive hashes in source-lock.json.
This command builds files only; it never installs or loads a kext.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/RembrandtGfx'
LOCK = json.loads((ROOT / 'source-lock.json').read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, directory, name):
    result = subprocess.run(args, cwd=directory, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (directory / (name + '.log')).write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(f'{name} failed:\n{result.stdout}')
    return result.stdout


def dependency(name):
    spec = LOCK['dependencies'][name]
    downloads = ROOT / 'build/downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / (name + '.tar.gz')
    if not archive.exists():
        print(f'Downloading {name} at {spec["commit"]}', flush=True)
        with urllib.request.urlopen(spec['archive_url'], timeout=60) as response:
            archive.write_bytes(response.read())
    if digest(archive) != spec['archive_sha256']:
        raise ValueError(f'{archive} does not match source-lock.json; remove it and retry')
    destination = ROOT / 'build/dependencies' / name
    marker = destination / '.archive-sha256'
    if marker.exists() and marker.read_text().strip() == spec['archive_sha256']:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    with tarfile.open(archive) as compressed:
        top = compressed.getnames()[0].split('/')[0]
        compressed.extractall(destination.parent)
    (destination.parent / top).rename(destination)
    marker.write_text(spec['archive_sha256'] + '\n')
    return destination


def prepare_firmware(source, build):
    expanded = build / 'firmware-inputs'
    expanded.mkdir(parents=True, exist_ok=True)
    for name, expected in LOCK['firmware']['files'].items():
        original = source / name
        if original.exists():
            data = original.read_bytes()
        else:
            original = source / (name + '.zst')
            if not original.exists():
                raise FileNotFoundError(f'Missing local firmware: {source / name} (or .zst)')
            if digest(original) != expected['zst_sha256']:
                raise ValueError(f'{original.name} differs from the recorded firmware')
            data = subprocess.check_output(['zstd', '-qdc', str(original)])
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError(f'{name} differs from the recorded firmware in source-lock.json')
        (expanded / name).write_bytes(data)
    extractor = ROOT / 'scripts/fw-extract.py'
    if digest(extractor) != LOCK['firmware']['extractor_sha256']:
        raise ValueError('Firmware extractor differs from the pinned upstream script')
    run([sys.executable, str(extractor), str(expanded), str(build / 'fw')], build, 'firmware')
    prepare_vcn(expanded / 'yellow_carp_vcn.bin', build)


def prepare_vcn(source, build):
    data = source.read_bytes()
    size, header_size, major, minor, _, _, version, length, offset, checksum = struct.unpack_from('<IIHHHHIIII', data)
    if size != len(data) or header_size != 32 or (major, minor) != (1, 0):
        raise ValueError('Unexpected VCN firmware header')
    if offset + length != len(data) or length > 0x100000:
        raise ValueError('Invalid VCN firmware payload range')
    payload = data[offset:offset + length]
    if zlib.crc32(payload) != checksum or payload[0xa0:0xa4] != b'AMD@':
        raise ValueError('VCN payload failed CRC or AMD marker validation')
    if struct.unpack_from('<I', payload, 0x60)[0] != version:
        raise ValueError('VCN payload version differs from its header')
    (build / 'fw/vcn.bin').write_bytes(payload)
    (build / 'vcn-firmware.json').write_text(json.dumps({
        'source_sha256': digest(source), 'payload_sha256': hashlib.sha256(payload).hexdigest(),
        'payload_bytes': length, 'version': hex(version), 'crc32': hex(checksum),
        'marker_and_version_match': True,
    }, indent=2) + '\n')


def compile_driver(build, sdk, lilu, generated, jobs):
    kernel = ['-target', 'x86_64-apple-macos10.15', '-mkernel', '-nostdinc', '-fno-builtin', '-fno-common',
              '-mno-red-zone', '-O2', '-fno-asynchronous-unwind-tables', '-DKERNEL', '-DKERNEL_PRIVATE',
              '-DDRIVER_PRIVATE', '-DAPPLE', '-DNeXT', '-I' + str(sdk / 'Headers'), '-I' + str(lilu)]
    cpp = kernel + ['-I' + str(generated), '-std=c++17', '-fapple-kext', '-nostdlib', '-fno-rtti',
                    '-fno-exceptions', '-fno-use-cxa-atexit', '-mllvm',
                    '-disable-atexit-based-global-dtor-lowering', '-DPRODUCT_NAME=RembrandtGfx',
                    '-DMODULE_VERSION=0.1.0', '-Wno-deprecated-declarations']
    names = 'kern_start mmio smu golden dmub display firmware probe vmwatch sleep usb4 umdpatch disklog vramcrc nvcopy'.split()
    sources = [(SOURCE / (name + '.cpp'), name) for name in names]
    sources.append((lilu / 'Library/plugin_start.cpp', 'plugin_start'))

    def compile_cpp(job):
        path, name = job
        run(['xcrun', 'clang++', *cpp, '-c', str(path), '-o', name + '.o'], build, name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(compile_cpp, sources))
    run(['xcrun', 'clang', *kernel, '-c', str(SOURCE / 'info.c'), '-o', 'info.o'], build, 'info')
    run(['xcrun', 'clang', '-target', 'x86_64-apple-macos10.15', '-c', str(SOURCE / 'fw.s'), '-o', 'fw.o'],
        build, 'firmware-assembly')
    objects = [name + '.o' for _, name in sources] + ['info.o', 'fw.o']
    run(['xcrun', 'ld', '-arch', 'x86_64', '-kext', '-platform_version', 'macos', '10.15', '10.15',
         '-no_data_const', '-o', 'RembrandtGfx', *objects, str(sdk / 'Library/x86_64/libkmod.a')], build, 'link')
    bundle = build / 'RembrandtGfx.kext/Contents'
    (bundle / 'MacOS').mkdir(parents=True, exist_ok=True)
    shutil.copy2(build / 'RembrandtGfx', bundle / 'MacOS/RembrandtGfx')
    shutil.copy2(SOURCE / 'Info.plist', bundle / 'Info.plist')
    plistlib.loads((bundle / 'Info.plist').read_bytes())
    return bundle / 'MacOS/RembrandtGfx'


def record_build(build, binary, reference):
    binary_format = run(['file', str(binary)], build, 'binary-format').strip()
    imports = run(['xcrun', 'nm', '-u', str(binary)], build, 'undefined-symbols')
    record = {
        'architecture': 'x86_64', 'format': binary_format,
        'binary_sha256': digest(binary), 'binary': str(binary.relative_to(build)),
        'source_sha256': {p.relative_to(ROOT).as_posix(): digest(p)
                          for p in sorted(SOURCE.iterdir()) if p.is_file()},
        'generated_header_sha256': digest(build / 'generated/command_staging.hpp'),
        'dependencies': LOCK['dependencies'],
        'validation': 'compiled and linked; no installation or runtime validation performed',
    }
    if reference:
        previous = subprocess.check_output(['xcrun', 'nm', '-u', str(reference)], text=True)
        record['reference_binary_sha256'] = digest(reference)
        record['additional_imports'] = sorted(set(imports.splitlines()) - set(previous.splitlines()))
        record['removed_imports'] = sorted(set(previous.splitlines()) - set(imports.splitlines()))
    (build / 'build-manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(binary_format)
    print(f'Built {binary.parent.parent.parent}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-dir', type=Path, required=True, help='local directory containing the recorded yellow_carp_*.bin or .bin.zst files')
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--metal-function', type=Path, help='local 1294-byte Tahoe Metal original function')
    inputs.add_argument('--metal-text', type=Path, help='local MTLDriver-Tahoe-TEXT.bin')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/RembrandtGfx')
    parser.add_argument('--reference-binary', type=Path, help='optional existing kext executable for an import comparison')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    build = args.output_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    generated = build / 'generated'
    native_option = '--function-bin' if args.metal_function else '--text-bin'
    run([sys.executable, str(ROOT / 'scripts/assemble-command-staging.py'), native_option,
         str((args.metal_function or args.metal_text).resolve()), '--output', str(generated / 'command_staging.hpp')],
        build, 'command-staging')
    sdk = dependency('MacKernelSDK')
    lilu = dependency('Lilu') / 'Lilu'
    prepare_firmware(args.firmware_dir.resolve(), build)
    binary = compile_driver(build, sdk, lilu, generated, args.jobs)
    reference = args.reference_binary.resolve() if args.reference_binary else None
    record_build(build, binary, reference)


if __name__ == '__main__':
    main()
