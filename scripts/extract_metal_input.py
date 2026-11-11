#!/usr/bin/env python3
"""Read the candidate 23 Metal input from a user's own Tahoe 25G332 x86_64h cache.

Reads local files only. The default output is build/private/metal-input;
no system files are changed and no Apple files are downloaded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import uuid

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = Path('/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld')
SYSTEM_VERSION = Path('/System/Library/CoreServices/SystemVersion.plist')
EXPECTED_BUILD = '25G332'
IMAGE_ADDRESS = 0x7FFB110D4000
EXPECTED_TEXT_SHA256 = '88a33d1bc471708f4d25f527a0bef7771f5ba6cd8d057ec3ee0d7cb16f772b9e'
LOCK = json.loads((ROOT / 'source-lock.json').read_text())['command_staging']


def read_at(path, offset, size):
    with path.open('rb') as stream:
        stream.seek(offset)
        data = stream.read(size)
    if len(data) != size:
        raise ValueError(f'Incomplete local cache read: {path.name} at {offset:#x}')
    return data


def cache_mappings(path):
    header = read_at(path, 0, 4096)
    if header[:16].rstrip(b'\0') != b'dyld_v1 x86_64h':
        raise ValueError('Expected the Tahoe x86_64h dyld cache, not an arm64 or other cache')
    offset, count = struct.unpack_from('<II', header, 16)
    table = read_at(path, offset, count * 32)
    return [struct.unpack_from('<QQQII', table, i * 32) for i in range(count)]


def read_vm(path, mappings, address, size):
    for start, length, offset, _, _ in mappings:
        if start <= address and address + size <= start + length:
            file_offset = offset + address - start
            return read_at(path, file_offset, size), file_offset
    raise ValueError('The local cache does not contain the verified 25G332 Metal image address')


def metal_header(data):
    magic, cpu, _, _, count, command_bytes, _, _ = struct.unpack_from('<IIIIIIII', data)
    if magic != 0xFEEDFACF or cpu != 0x1000007:
        raise ValueError('The Metal image is not an x86_64 Mach-O')
    if 32 + command_bytes > len(data):
        raise ValueError('Metal load commands exceed the header read')
    position = 32
    ident = None
    text_address = None
    text_size = None
    for _ in range(count):
        command, length = struct.unpack_from('<II', data, position)
        if length < 8 or position + length > 32 + command_bytes:
            raise ValueError('Invalid Metal load command')
        if command == 0x1B:
            ident = str(uuid.UUID(bytes=data[position + 8:position + 24])).upper()
        elif command == 0x19:
            _, _, name, address, _, _, file_size, _, _, _, _ = struct.unpack_from('<II16sQQQQIIII', data, position)
            if name.rstrip(b'\0') == b'__TEXT':
                text_address, text_size = address, file_size
        position += length
    if ident != LOCK['native_uuid'] or text_address != IMAGE_ADDRESS or text_size != 5145968:
        raise ValueError('The Metal image UUID or TEXT layout does not match candidate 23 / 25G332')
    return ident, text_address, text_size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, default=CACHE_DIR, help='local Tahoe cache directory')
    parser.add_argument('--system-version-plist', type=Path, default=SYSTEM_VERSION,
                        help='SystemVersion.plist belonging to the same local Tahoe installation')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/private/metal-input')
    parser.add_argument('--write-text', action='store_true', help='also save the local complete TEXT segment')
    args = parser.parse_args()
    version = plistlib.loads(args.system_version_plist.read_bytes())
    actual_build = version.get('ProductBuildVersion')
    if actual_build != EXPECTED_BUILD:
        parser.error(f'Expected Tahoe build {EXPECTED_BUILD}; supplied system is {actual_build}. No input was written.')
    cache = args.cache_dir / 'dyld_shared_cache_x86_64h.03'
    if not cache.is_file():
        parser.error(f'Missing local cache: {cache}. Use --cache-dir for your own matching installation.')
    mappings = cache_mappings(cache)
    header, _ = read_vm(cache, mappings, IMAGE_ADDRESS, 8192)
    ident, address, size = metal_header(header)
    text, file_offset = read_vm(cache, mappings, address, size)
    text_hash = hashlib.sha256(text).hexdigest()
    if text_hash != EXPECTED_TEXT_SHA256:
        raise ValueError('The local immutable Metal TEXT differs from the verified 25G332 image')
    start = int(LOCK['native_text_offset'], 16)
    function = text[start:start + LOCK['size']]
    function_hash = hashlib.sha256(function).hexdigest()
    if len(function) != LOCK['size'] or function_hash != LOCK['original_sha256']:
        raise ValueError('The complete Metal function differs from the candidate 23 input')
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    function_path = output / 'render-writer-original.bin'
    function_path.write_bytes(function)
    if args.write_text:
        (output / 'MTLDriver-Tahoe-TEXT.bin').write_bytes(text)
    manifest = {
        'system_build': actual_build, 'image_uuid': ident, 'cache': str(cache.resolve()),
        'cache_text_file_offset': hex(file_offset), 'text_bytes': size, 'text_sha256': text_hash,
        'function_text_offset': LOCK['native_text_offset'], 'function_bytes': len(function),
        'function_sha256': function_hash, 'function_file': function_path.name,
        'source': 'local immutable dyld cache; no process memory read or system modification',
    }
    (output / 'metal-input.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Extracted {function_path}')
    print(f'Build {actual_build}; UUID {ident}; {len(function)} bytes; SHA-256 {function_hash}')


if __name__ == '__main__':
    main()
