#!/usr/bin/env python3
"""Generate command_staging.hpp from a local Tahoe 25G332 Metal function.

Apple machine code, disassembly and generated arrays stay in the local work directory.
The input must match the complete function used by candidate 23.
"""
import argparse
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess
import tempfile

START = 0x7FFB111DCAE6
SIZE = 1294
TEXT_OFFSET = 0x108AE6
NATIVE_UUID = 'F89F483D-39AC-368D-B9D9-FB689179EFD2'
ORIGINAL_SHA256 = 'f49c9d6d8cd0ad91aefefe857554f2d9e1c0e9d2fdbde75110100fc057e141dd'
REPLACEMENT_SHA256 = '37d7b6c5671f9df8b25b02a9cdc2d951e29b5e46ead7d13f1161c38b78074a07'


def text_section(path):
    data = path.read_bytes()
    position = 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, position)
        if command == 0x19:
            count = struct.unpack_from('<I', data, position + 64)[0]
            for i in range(count):
                section = struct.unpack_from('<16s16sQQIIIIIIII', data, position + 72 + 80 * i)
                if section[0].rstrip(b'\0') == b'__text':
                    if section[7] != 0:
                        raise ValueError('Replacement has relocations')
                    return data[section[4]:section[4] + section[3]]
        position += size
    raise ValueError('No text section')


def compile_assembly(directory, name, lines):
    source = directory / (name + '.S')
    source.write_text('.text\n.globl _rmb_writer\n_rmb_writer:\n' + '\n'.join(lines) + '\n')
    output = directory / (name + '.o')
    result = subprocess.run(['xcrun', 'clang', '-arch', 'x86_64', '-c', str(source), '-o', str(output)],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return text_section(output)


def disassemble(raw, directory):
    # A local single-section Mach-O gives otool the original instruction addresses.
    offset = 32 + 72 + 80
    mach_header = struct.pack('<IIIIIIII', 0xFEEDFACF, 0x1000007, 3, 1, 1, 152, 0, 0)
    segment = struct.pack('<II16sQQQQIIII', 0x19, 152, b'__TEXT', START, len(raw),
                          offset, len(raw), 7, 5, 1, 0)
    section = struct.pack('<16s16sQQIIIIIIII', b'__text', b'__TEXT', START, len(raw),
                          offset, 0, 0, 0, 0x80000400, 0, 0, 0)
    native = directory / 'native-function.macho'
    native.write_bytes(mach_header + segment + section + raw)
    result = subprocess.run(['xcrun', 'otool', '-tv', str(native)], check=True,
                            capture_output=True, text=True)
    rows = []
    for line in result.stdout.splitlines():
        match = re.match(r'^([0-9a-f]+)\t([^\t]+)(?:\t(.*))?$', line)
        if match:
            operands = (match[3] or '').split('##', 1)[0].strip()
            rows.append({'address': int(match[1], 16), 'operation': match[2], 'operands': operands})
    if not rows or rows[0]['address'] != START:
        raise ValueError('otool did not decode the expected function')
    for i, row in enumerate(rows):
        end = rows[i + 1]['address'] if i + 1 < len(rows) else START + SIZE
        row['bytes'] = raw[row['address'] - START:end - START]
    return rows


def add_displacement(memory, value):
    match = re.fullmatch(r'(-?0x[0-9a-f]+)?(\(.+\))', memory)
    assert match, memory
    displacement = int(match[1] or '0', 16) + value
    prefix = (('-' if displacement < 0 else '') + hex(abs(displacement))) if displacement else ''
    return prefix + match[2]


def transform(raw, rows, directory):
    replacements = {
        # RBX and R9 + targetIndex * 80 point at the same colour-target state.
        0x7FFB111DCB29: (0x7FFB111DCB34, ['movq %rbx, %r15']),
        # The colour-target index is 0..7 and 0x390 has its low three bits clear.
        0x7FFB111DCB70: (0x7FFB111DCB7A, ['leal 0x390(%r10), %r13d']),
        # The extra bytes land on later packet headers, which the native body overwrites.
        0x7FFB111DCD13: (0x7FFB111DCD2D, ['vmovups 0x5ec(%rsi), %ymm0', 'vmovups %ymm0, -0x58(%rdx)', 'addq $0x18, %rdx']),
        0x7FFB111DCD3B: (0x7FFB111DCD55, ['vmovups 0x604(%rsi), %ymm0', 'vmovups %ymm0, -0x50(%rdx)', 'addq $0x14, %rdx']),
        # The fixed sixteen-word loop makes R8=-64 solely to calculate this return offset.
        0x7FFB111DCF49: (0x7FFB111DCF4C, []),
        0x7FFB111DCF5C: (0x7FFB111DCF60, []),
        0x7FFB111DCF9D: (0x7FFB111DCFA3, ['leaq 0x40(%rdx), %rax']),
    }
    single_headers = []
    for i, row in enumerate(rows[:-1]):
        match = re.fullmatch(r'\$(0x[0-9a-f]+), (%r\w+)', row['operands'])
        if row['operation'] != 'movabsq' or not match:
            continue
        value = int(match[1], 16)
        following = rows[i + 1]
        if value & 0xFFFFFFFF != 0xC0016900 or following['operation'] != 'movq':
            continue
        prefix = match[2] + ', '
        assert following['operands'].startswith(prefix)
        memory = following['operands'][len(prefix):]
        replacement = ['movl %r11d, ' + memory,
                       'movl $' + hex(value >> 32) + ', ' + add_displacement(memory, 4)]
        replacements[row['address']] = (following['address'] + len(following['bytes']), replacement)
        single_headers.append(hex(row['address'] - START))
    assert len(single_headers) == 13, single_headers

    original, staged = [], []
    removed = set()
    for row in rows:
        label = 'L_old_' + format(row['address'] - START, '04x')
        operands = row['operands']
        if row['operation'].startswith('j'):
            target = int(operands, 16)
            assert START <= target < START + SIZE
            operands = 'L_old_' + format(target - START, '04x')
        instruction = row['operation'] + (' ' + operands if operands else '')
        original += [label + ':', instruction]
        if any(begin < row['address'] < end for begin, (end, _) in replacements.items()):
            removed.add(row['address'])
            continue
        if row['address'] == START + 13:
            staged += ['subq $0x1008, %rsp', 'movq %rdx, -0x30(%rbp)', 'movq %rsp, %rdx']
        if row['address'] == 0x7FFB111DCFE9:
            # At least the first 28 bytes and eight 136-byte targets are always emitted.
            staged += ['leaq -31(%rax), %rcx', 'movq -0x30(%rbp), %rdi', 'movq %rsp, %rsi',
                       'subq %rsi, %rax', 'addq %rdi, %rax', 'L_bulk_copy:',
                       'vmovups (%rsi), %ymm0', 'vmovups %ymm0, (%rdi)',
                       'addq $32, %rsi', 'addq $32, %rdi', 'cmpq %rsi, %rcx', 'ja L_bulk_copy',
                       'movq %rax, %rcx', 'subq %rdi, %rcx', 'shrq $2, %rcx', 'rep movsl',
                       'addq $0x1008, %rsp', 'vzeroupper']
        staged.append(label + ':')
        staged.extend(replacements.get(row['address'], (None, [instruction]))[1])
    for row in rows:
        if row['address'] in removed or not row['operation'].startswith('j'):
            continue
        if any(begin <= row['address'] < end for begin, (end, _) in replacements.items()):
            continue
        assert int(row['operands'], 16) not in removed

    rebuilt = compile_assembly(directory, 'render-writer-reassembled', original)
    assert rebuilt == raw, 'Reassembly must reproduce the original bytes before transforming'
    code = compile_assembly(directory, 'render-writer-staged', staged)
    assert len(code) <= SIZE, f'Replacement too large: {len(code)} > {SIZE}'
    padded = code + b'\x90' * (SIZE - len(code))
    manifest = {'native_uuid': NATIVE_UUID, 'native_text_offset': '0x108ae6',
                'original_size': SIZE, 'replacement_size': len(code), 'padded_size': len(padded),
                'original_sha256': hashlib.sha256(raw).hexdigest(), 'replacement_sha256': hashlib.sha256(padded).hexdigest(),
                'original_reassembly_identical': True, 'stack_allocation_bytes': 4104,
                'single_header_sites': single_headers, 'relocations': 0,
                'status': 'generated locally; no runtime validation performed by this tool'}
    if manifest['replacement_sha256'] != REPLACEMENT_SHA256:
        raise ValueError('Generated replacement differs from candidate 23')
    return padded, manifest


def write_header(output, original, replacement):
    def array(name, data):
        lines = ['\t' + ', '.join(f'0x{x:02x}' for x in data[i:i + 16]) + ','
                 for i in range(0, len(data), 16)]
        return f'constexpr uint8_t {name}[] {{\n' + '\n'.join(lines) + '\n};\n'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('// Generated by assemble-command-staging.py; native UUID ' + NATIVE_UUID + '.\n'
                      '#pragma once\n#include <stdint.h>\nnamespace RmbCommandStaging {\n'
                      + array('original', original) + array('replacement', replacement)
                      + 'static_assert(sizeof(original) == sizeof(replacement));\n}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--function-bin', type=Path, help='local 1294-byte original function')
    inputs.add_argument('--text-bin', type=Path, help='local MTLDriver-Tahoe-TEXT.bin (function at 0x108ae6)')
    parser.add_argument('--output', type=Path, required=True, help='local generated command_staging.hpp')
    args = parser.parse_args()
    raw = (args.function_bin or args.text_bin).read_bytes()
    if args.text_bin:
        raw = raw[TEXT_OFFSET:TEXT_OFFSET + SIZE]
    if len(raw) != SIZE or hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Input does not match the Tahoe 25G332 function; expected SHA-256 ' + ORIGINAL_SHA256)
    # Temporary originals and complete assembly are never part of the published source tree.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='command-staging-', dir=args.output.parent) as temporary:
        directory = Path(temporary)
        rows = disassemble(raw, directory)
        replacement, manifest = transform(raw, rows, directory)
    write_header(args.output, raw, replacement)
    args.output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
