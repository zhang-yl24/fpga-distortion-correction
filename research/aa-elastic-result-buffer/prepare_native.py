#!/usr/bin/env python3
"""Authenticate a private canonical seed and prepare native inputs; optionally elaborate the system.
Never executes a simulation, vendor tools, network commands or publication.
Python 3.10+. Checks do not use assert and remain enabled with python -O.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time

HERE = Path(__file__).absolute().parent
RECIPE_PART_SHA256 = {'metadata/SEED_FILES.json': '970d93c837b5d32968ea99d2b1d486afa86c6f5e41d52d1e06b7093c55d06b18', 'metadata/NORMALIZATION.json': '434138737315c7f5983fa5fb6150e2edb1e4d77c7c1575625e52004a82cdcdc7', 'metadata/NATIVE_RECIPE.json': '73d7fff57167a6071b3623b2a17fe79246248e592c3d28524d3c9cfc4f57b5f1'}
sys.dont_write_bytecode = True

class Refusal(RuntimeError):
    pass

def need(ok, message):
    if not ok:
        raise Refusal(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def rel(name):
    need(isinstance(name, str) and bool(name), 'invalid relative name')
    need(not any(ord(c) < 32 for c in name), 'control character in relative name')
    need(not any(c in name for c in '\\:{}'), 'unsupported relative name')
    p = PurePosixPath(name)
    need(not p.is_absolute() and all(x not in ('', '.', '..') for x in name.split('/')), 'traversal or absolute name')
    need(str(p) == name, 'noncanonical relative name')
    return name

def checked(value, exists=True, directory=None):
    need('..' not in Path(value).parts, 'path traversal refused')
    p = Path(os.path.abspath(value))
    need(not any(ord(c) < 32 for c in str(p)), 'control character in path')
    for q in [*reversed(p.parents), p]:
        if not os.path.lexists(q):
            continue
        s = q.lstat()
        need(not stat.S_ISLNK(s.st_mode), 'symlink refused')
        need(not (getattr(s, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)), 'reparse point refused')
        need(not getattr(q, 'is_junction', lambda: False)(), 'junction refused')
        if q != p:
            need(stat.S_ISDIR(s.st_mode), 'non-directory ancestor')
    need(not exists or p.exists(), 'required path missing')
    if p.exists() and directory is not None:
        need(p.is_dir() if directory else p.is_file(), 'wrong input type')
    return p

def read(path):
    p = checked(path, directory=False)
    fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        s = os.fstat(fd)
        need(stat.S_ISREG(s.st_mode), 'special file refused')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            data = f.read()
        t = os.fstat(fd)
        need((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns) == (t.st_dev, t.st_ino, t.st_size, t.st_mtime_ns), 'input changed during read')
        return data
    finally:
        os.close(fd)

def auth(path, digest):
    data = read(path)
    need(sha(data) == digest, 'input hash mismatch: ' + Path(path).name)
    return data

def json_load(data):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    return json.loads(data, object_pairs_hook=pairs)

def dump(obj):
    return (json.dumps(obj, indent=2, sort_keys=True) + '\n').encode()

def inventory(root):
    checked(root, directory=True)
    names = set()
    for parent, dirs, files in os.walk(root, followlinks=False):
        for n in dirs + files:
            p = checked(Path(parent) / n)
            need(p.is_dir() or p.is_file(), 'special tree entry refused')
        for n in files:
            names.add(rel((Path(parent) / n).relative_to(root).as_posix()))
    return names

def verify_package():
    manifest = json_load(read(HERE / 'PUBLIC_MANIFEST.json'))
    need(inventory(HERE) == set(manifest) | {'PUBLIC_MANIFEST.json'}, 'public package inventory differs')
    for name, digest in manifest.items():
        auth(HERE / rel(name), digest)
    return len(manifest)

def normalized(raw, prefix):
    # Exactly the previously tested include-location normalization, not a source edit.
    return raw.replace(prefix, b'')

def board_patch(portable):
    changes = [
        (b'module board1080_top #(', b'module board1080_elastic_research_top #('),
        (b'    hdmi1080_video_system_run8_research #(\n', b'    hdmi1080_video_system_elastic_research #(\n        .ENABLE_ELASTIC_BUFFER(1),\n'),
        (b'        .RESULT_BANKS(2),', b'        .RESULT_BANKS(3),'),
    ]
    out = portable
    for old, new in changes:
        need(out.count(old) == 1, 'board patch anchor count differs')
        out = out.replace(old, new, 1)
    inverse = out
    for old, new in reversed(changes):
        inverse = inverse.replace(new, old, 1)
    need(inverse == portable, 'board patch inverse mismatch')
    return out

def inspect(native):
    files_verified = verify_package()
    recipe = {}
    for name, digest in RECIPE_PART_SHA256.items():
        section = json_load(auth(HERE / name, digest))
        need(not set(recipe) & set(section), 'duplicate recipe sections')
        recipe.update(section)
    native = checked(native, directory=True)
    manifest_raw = auth(native.parent / 'NATIVE_SOURCE_MANIFEST.json', recipe['canonical_manifest_sha256'])
    manifest = json_load(manifest_raw)
    prefix = (manifest['BaseDirectory'].replace('\\', '/') + '/').encode()
    expected = {rel(f['path']): f for f in recipe['canonical_files']}
    need(len(expected) == 164 and inventory(native) == set(expected), 'exact 164-file canonical seed required')
    need({x['path']: x['sha256'] for x in manifest['files']} == {p: x['sha256'] for p, x in expected.items()}, 'canonical manifest content differs')
    raw = {p: auth(native / p, f['sha256']) for p, f in expected.items()}
    need(all(len(raw[p]) == f['bytes'] for p, f in expected.items()), 'canonical size differs')
    records = {p: auth(native.parent / rel(p), h) for p, h in recipe['record_hashes'].items()}
    refs = {}
    for f in recipe['reference_files']:
        p = rel(f['path']); need(sha(raw[p]) == f['raw_sha256'], 'reference raw hash mismatch')
        refs[p] = normalized(raw[p], prefix)
        need(sha(refs[p]) == f['normalized_sha256'], 'reference normalization mismatch')
    need(len(refs) == 85, 'reference inventory differs')
    derived = dict(raw)
    for f in recipe['native_normalized_files']:
        p = rel(f['path']); need(sha(raw[p]) == f['raw_sha256'], 'native raw hash mismatch')
        derived[p] = normalized(raw[p], prefix)
        need(sha(derived[p]) == f['normalized_sha256'], 'native normalization mismatch')
    base_overlay = {}
    for folder in ['rtl', 'telemetry/rtl']:
        for p in sorted((HERE / 'overlay' / folder).glob('*.sv')):
            base_overlay[folder + '/' + p.name] = read(p)
    need(len(base_overlay) == 11, 'overlay inventory differs')
    for name, h in recipe['added_modules'].items():
        matches = [data for p, data in base_overlay.items() if Path(p).name == Path(name).name]
        need(len(matches) == 1 and sha(matches[0]) == h, 'added module identity differs')
        derived[rel(name)] = matches[0]
    original_top = recipe['original_board_top_path']
    portable_top = normalized(raw[original_top], prefix)
    need(sha(portable_top) == recipe['portable_original_top_sha256'], 'board portable identity differs')
    del derived[original_top]
    top = board_patch(portable_top)
    need(sha(top) == recipe['new_board_top_sha256'], 'board overlay identity differs')
    derived[rel(recipe['new_board_top_path'])] = top
    need(len(derived) == 174, 'derived inventory differs')
    for p, h in recipe['native_payload_sha256'].items():
        data = records['inputs/KEY1_ONLY.fdc'] if p == 'payload/inputs/KEY1_ONLY.fdc' else derived[rel(p.removeprefix('payload/native/'))]
        need(sha(data) == h, 'original native payload manifest mismatch')
    need(len(recipe['native_payload_sha256']) == 97, 'native payload count differs')
    imports = recipe['import_plan']['imports']
    need(len(imports) == 85 and len({x['path'] for x in imports}) == 85, '85 unique native imports required')
    need(all(x['path'] in derived for x in imports) and original_top not in [x['path'] for x in imports], 'native imports unresolved')
    rom = recipe['import_plan']['rom']
    need(len(derived[rom['source']]) == rom['bytes'] and sha(derived[rom['source']]) == rom['sha256'], 'ROM identity differs')
    for c in recipe['import_plan']['constraints']:
        need(c['path'] in (records if c['origin'] == 'private_record' else derived), 'constraint input missing')
    return {'recipe': recipe, 'raw': raw, 'records': records, 'refs': refs, 'derived': derived,
            'base_overlay': base_overlay,
            'summary': {'public_files_verified': files_verified, 'raw_seed_files_verified': 164,
                        'reference_raw_to_normalized_verified': 85, 'derived_native_files_verified': 174,
                        'original_native_payload_hashes_verified': 97, 'unique_native_imports': 85,
                        'board_patch_inverse_byte_equal': True, 'private_seed_required': True,
                        'full_camera_replay_available': False, 'any_simulation_executed': False,
                        'PDS_executed': False}}

def output_path(value, native):
    out = checked(value, exists=False)
    need(not os.path.lexists(out), 'output exists; overwrite refused')
    checked(out.parent, directory=True)
    for protected in (native.parent, HERE):
        need(not out.is_relative_to(protected) and not protected.is_relative_to(out), 'output overlaps seed/package')
    return out

def put(root, name, data):
    p = root / rel(name)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    checked(p.parent, directory=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as f: f.write(data)

def generate(info, native, out, compiler=None):
    out = output_path(out, native); out.mkdir(mode=0o700)
    put(out, 'PRIVATE_DO_NOT_PUBLISH.txt', b'Private licensed seed derivatives. Never publish or upload this generated tree.\nNo simulation or vendor tools are executed by this helper.\n')
    for name, data in info['derived'].items(): put(out, 'native/' + name, data)
    put(out, 'inputs/KEY1_ONLY.fdc', info['records']['inputs/KEY1_ONLY.fdc'])
    put(out, 'IMPORT_PLAN.json', dump(info['recipe']['import_plan']))
    rom = info['recipe']['import_plan']['rom']
    put(out, 'run/' + rel(rom['working_filename']), info['derived'][rom['source']])
    summary = dict(info['summary'], status='PASS_PRIVATE_NATIVE_PREPARATION_ONLY', strict_compile_executed=False)
    need(inventory(out / 'native') == set(info['derived']), 'private native inventory differs')
    for p, data in info['derived'].items(): need(read(out / 'native' / p) == data, 'derived readback mismatch')
    if compiler:
        # A system-only strict elaboration: never run the simulator or claim PDS TOP closure.
        compiler = checked(compiler, directory=False)
        for name, data in info['refs'].items(): put(out, 'strict_inputs/reference/' + name, data)
        for name, data in info['base_overlay'].items(): put(out, 'strict_inputs/' + name, data)
        ref = out / 'strict_inputs/reference'
        sources = sorted(p for p in ref.rglob('*') if p.suffix in ('.v', '.sv')) + sorted((out / 'strict_inputs/rtl').glob('*.sv')) + sorted((out / 'strict_inputs/telemetry/rtl').glob('*.sv'))
        incs = [ref, out / 'strict_inputs/rtl'] + sorted({p.parent for p in ref.rglob('*.vh')})
        top = 'hdmi1080_video_system_elastic_research'
        params = info['recipe']['static_system_parameters']
        need(params['ENABLE_ELASTIC_BUFFER'] == 1 and params['RESULT_BANKS'] == 3, 'native elastic parameters differ')
        binary = out / 'strict.vvp'
        cmd = [str(compiler), '-g2012', '-Wall', '-s', top, '-o', str(binary)]
        cmd += [v for p in incs for v in ('-I', str(p))]
        cmd += [v for k, value in sorted(params.items()) for v in ('-P', top + '.' + k + '=' + str(value))]
        cmd += list(map(str, sources))
        start = time.monotonic()
        try:
            run = subprocess.run(cmd, cwd=out / 'run', capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise Refusal('strict compiler exceeded 120 seconds; no simulation was run')
        log = run.stdout + run.stderr
        put(out, 'strict_compile.log', log.replace(str(out), '<PRIVATE_NATIVE>').replace(str(compiler), '<IVERILOG>').encode())
        need(run.returncode == 0, 'strict compile failed; inspect private strict_compile.log')
        need(not any(x in log for x in ['implicit definition', 'Unknown module', 'expects ']), 'strict binding warning/error')
        modules = sorted(set(re.findall(r'\.scope module, "[^\"]+" "([^\"]+)"', read(binary).decode())))
        required = {'hdmi1080_video_system_elastic_research', 'hdmi1080_video_system_elastic_enabled_research', 'hdmi1080_capture_cdc', 'hdmi1080_input_dma', 'ddr_write_arbiter', 'elastic_result_owner_integrated_research', 'pipeline_brown_run8_key1_research', 'ddr_read_arbiter', 'ddr_video_reader_crc5_local', 'video_display_async_fifo', 'ddr_video_output_result_slot_research'}
        need(required <= set(modules) and 'hdmi1080_video_system_run8_research' not in modules, 'strict resolved module mismatch')
        binary.unlink()
        summary.update(status='PASS_PRIVATE_NATIVE_SYSTEM_ELABORATION_ONLY', strict_compile_executed=True,
                       compile_seconds=round(time.monotonic() - start, 4), compile_returncode=0,
                       required_modules_resolved=True, compiled_binary_removed=True,
                       warning_count=log.count('warning:'), simulation_binary_executed=False,
                       board_top_or_vendor_primitives_elaborated=False)
    # Recheck the input and generated identities after all optional work.
    for p, data in info['raw'].items(): need(read(native / p) == data, 'seed changed during operation')
    for p, data in info['derived'].items(): need(read(out / 'native' / p) == data, 'generated native changed')
    for p, data in info['records'].items(): need(read(native.parent / p) == data, 'private record changed')
    summary['seed_and_native_inputs_unchanged_after_operation'] = True
    put(out, 'PRIVATE_FILES_SHA256.json', dump({p: sha(read(out / p)) for p in sorted(inventory(out))}))
    put(out, 'PREPARATION_RESULT.json', dump(summary))
    return summary

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', type=Path, required=True, help='Exact authorized canonical ON/native directory')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--dry-run', action='store_true')
    g.add_argument('--out', type=Path, help='New private directory outside package and seed; parent must exist')
    p.add_argument('--iverilog', type=Path, help='Explicit trusted local Icarus compiler; requires --out; system elaboration only')
    a = p.parse_args()
    try:
        need(not a.iverilog or a.out is not None, '--iverilog requires --out')
        native = checked(a.native, directory=True)
        if a.out is not None: output_path(a.out, native)
        info = inspect(native)
        result = generate(info, native, a.out, a.iverilog) if a.out else dict(info['summary'], status='PASS_DRY_RUN_NO_WRITES')
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (Refusal, OSError, ValueError, KeyError, TypeError) as e:
        print('REFUSED: ' + str(e), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
