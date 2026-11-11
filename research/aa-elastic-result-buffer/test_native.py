#!/usr/bin/env python3
"""Short native-preparation integrity tests. No simulation or vendor tool runs."""
import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
sys.dont_write_bytecode = True
import prepare_native as p
import check_public_bundle as c

HERE = Path(__file__).absolute().parent

def run_tests(native, work):
    results = []
    def test(name, fn, refusal=False):
        try:
            fn()
            if refusal: raise RuntimeError('expected refusal did not happen')
        except p.Refusal:
            if not refusal: raise
        results.append({'test': name, 'status': 'PASS'})
    test('exact_public_inventory_hashes_and_content_scan', lambda: c.check(HERE))
    info = p.inspect(native)
    test('exact_164_seed_174_native_85_imports_97_payload', lambda: p.need(info['summary']['derived_native_files_verified'] == 174 and info['summary']['unique_native_imports'] == 85, 'wrong count'))
    for bad in ['', '../x', 'x/../y', '/abs', 'C:/abs', 'a\\b', 'a//b', './a', 'a\nq', 'a:{q}']:
        test('reject_relative_name_' + str(len(results)), lambda bad=bad: p.rel(bad), True)
    test('duplicate_json_keys', lambda: p.json_load(b'{"a":1,"a":2}'), True)
    test('board_patch_wrong_anchor', lambda: p.board_patch(b'module unrelated; endmodule'), True)
    test('bad_normalization_hash', lambda: p.need(p.sha(p.normalized(b'wrong', b'prefix/')) == info['recipe']['reference_files'][0]['normalized_sha256'], 'normalized mismatch'), True)
    with tempfile.TemporaryDirectory(prefix='native_tests_', dir=work) as t:
        t = Path(t)
        seed = t / 'seed/native'; shutil.copytree(native, seed)
        for n in ['NATIVE_SOURCE_MANIFEST.json', 'MAP_PREPARED.tcl', 'inputs/KEY1_ONLY.fdc']:
            q = seed.parent / n; q.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(native.parent / n, q)
        chosen = info['recipe']['canonical_files'][0]['path']; q = seed / chosen; original = q.read_bytes()
        q.write_bytes(original + b' ')
        test('changed_seed_refused', lambda: p.inspect(seed), True)
        q.unlink(); test('missing_seed_file_refused', lambda: p.inspect(seed), True)
        q.write_bytes(original); (seed / 'unexpected.txt').write_bytes(b'x')
        test('extra_seed_file_refused', lambda: p.inspect(seed), True)
        (seed / 'unexpected.txt').unlink(); q.unlink(); q.symlink_to(native / chosen)
        test('symlink_seed_file_refused', lambda: p.inspect(seed), True)
        q.unlink(); q.write_bytes(original)
        test('existing_output_refused', lambda: p.output_path(t, native), True)
        test('output_in_seed_refused', lambda: p.output_path(seed / 'output', seed), True)
        test('output_in_package_refused', lambda: p.output_path(HERE / 'output', native), True)
        link = t / 'linked'; link.symlink_to(seed, target_is_directory=True)
        test('symlink_native_root_refused', lambda: p.inspect(link), True)
        def cli(mode, expect, root=HERE, extra=None):
            cmd = [sys.executable, '-B'] + (['-O'] if mode else []) + [str(root / 'prepare_native.py'), '--native', str(seed), '--dry-run'] + (extra or [])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            p.need(r.returncode == expect, 'unexpected CLI status: ' + r.stderr[:200])
            return r
        test('normal_python_positive_cli', lambda: cli(False, 0))
        test('optimized_python_positive_cli', lambda: cli(True, 0))
        q.write_bytes(original + b'!')
        test('normal_python_identity_refusal', lambda: cli(False, 2))
        test('optimized_python_identity_refusal', lambda: cli(True, 2))
        q.write_bytes(original)
        test('compiler_cannot_run_with_dry_run', lambda: cli(False, 2, extra=['--iverilog', str(sys.executable)]))
        copy = t / 'package'; shutil.copytree(HERE, copy)
        def refresh(root):
            m = {x.relative_to(root).as_posix(): p.sha(x.read_bytes()) for x in root.rglob('*') if x.is_file() and x.name != 'PUBLIC_MANIFEST.json'}
            (root / 'PUBLIC_MANIFEST.json').write_bytes(p.dump(m))
        for name in p.RECIPE_PART_SHA256:
            entry = copy / name; old = entry.read_bytes(); entry.write_bytes(old + b' '); refresh(copy)
            test('recipe_pin_refuses_resealed_' + entry.name, lambda: cli(True, 2, copy))
            entry.write_bytes(old); refresh(copy)
        (copy / 'unexpected.txt').write_bytes(b'x')
        test('extra_public_file_refused', lambda: c.check(copy), True)
        (copy / 'unexpected.txt').unlink()
        target = copy / 'overlay/rtl/elastic_result_owner_research.sv'; target.write_bytes(target.read_bytes() + b' ')
        test('changed_public_rtl_refused', lambda: c.check(copy), True)
        for name, blob in [('compiler_source_excerpt', b'  42 | synthetic source'), ('proprietary_notice', b'PAN' + b'GO PROPRIETARY'), ('private_path', b'/' + b'workspace/secret'), ('encrypted_marker', b'`pragma ' + b'protect')]:
            test('scanner_rejects_' + name, lambda blob=blob: c.scan_bytes('fixture.txt', blob, {'scanned_files':0,'scanned_bytes':0,'nested_archives':0}), True)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z: z.writestr('inner.txt', b'clean data')
        test('nested_archive_refused', lambda: c.scan_bytes('nested.bin', stream.getvalue(), {'scanned_files':0,'scanned_bytes':0,'nested_archives':0}), True)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z: z.writestr('../traversal', b'clean data')
        test('nested_zip_traversal_refused', lambda: c.scan_bytes('nested.bin', stream.getvalue(), {'scanned_files':0,'scanned_bytes':0,'nested_archives':0}), True)
        generated = t / 'generated'
        result = p.generate(info, native, generated)
        test('fresh_private_preparation_174_byte_equal', lambda: p.need(p.inventory(generated / 'native') == set(info['derived']) and all(p.read(generated / 'native' / n) == b for n,b in info['derived'].items()), 'generated mismatch'))
        test('private_output_cannot_be_overwritten', lambda: p.generate(info, native, generated), True)
        test('camera_replay_not_claimed', lambda: p.need(result['full_camera_replay_available'] is False and not (generated / 'camera').exists(), 'camera scope differs'))
    p.inspect(native)
    return {'status':'PASS_SHORT_NATIVE_TESTS', 'tests_passed':len(results), 'tests':results,
            'any_simulation_executed':False, 'PDS_executed':False, 'original_seed_unchanged_after_tests':True}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True); parser.add_argument('--work', type=Path, required=True)
    a = parser.parse_args(); native = p.checked(a.native, directory=True); work = p.checked(a.work, directory=True)
    p.need(not work.is_relative_to(HERE) and not work.is_relative_to(native.parent), 'test work must be outside package and seed')
    print(json.dumps(run_tests(native, work), indent=2))

if __name__ == '__main__': main()
