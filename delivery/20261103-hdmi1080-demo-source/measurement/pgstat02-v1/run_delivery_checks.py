"""Verify exact authored inputs and run their 34 memory-only tests in Temp.

No serial library, COM, FPGA configuration, EDA or Library operation is used.
The source-only delivery omits the historical embedded v0 ZIP and uses this
runner instead of the author's whole-archive preservation runner.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch-parent',type=Path,
                        help='Existing writable directory for isolated test inputs')
    args=parser.parse_args()
    provenance=json.loads((ROOT/'AUTHOR_SOURCE_PROVENANCE.json').read_text(encoding='utf-8'))
    assert provenance['version']==1 and provenance['original_file_verified']
    rows=provenance['exact_copied_author_files']
    for row in rows:
        path=(ROOT/row['path']).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(),row['path']
        data=path.read_bytes()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],row['path']
    native=json.loads((ROOT/'reference/NATIVE_SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    hashes={r['path']:r['sha256'] for r in native['files']}
    for row in provenance['six_rtl_semantics_bindings']:
        assert hashes[row['native_source']]==row['sha256']
    temporary_root=(args.scratch_parent or Path(tempfile.gettempdir())).resolve(strict=True)
    assert temporary_root.is_dir(),temporary_root
    with tempfile.TemporaryDirectory(prefix='pgstat-v1-',dir=str(temporary_root)) as temporary:
        scratch=Path(temporary).resolve()
        assert scratch.is_relative_to(temporary_root) and scratch.name.startswith('pgstat-v1-')
        for row in rows:
            target=scratch/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/row['path'],target)
        sys.path[:0]=[str(scratch/'host'),str(scratch/'tests')]
        suite=unittest.defaultTestLoader.discover(str(scratch/'tests'),pattern='test_*.py')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        assert result.wasSuccessful() and result.testsRun==34
        assert 'serial' not in sys.modules,'Offline tests imported serial'
        print(json.dumps({'status':'PASS_DELIVERY_OFFLINE_MEMORY_TESTS','tests':result.testsRun,
            'exact_authored_files_verified':len(rows),'rtl_semantics_bindings':6,
            'source_archive_sha256':provenance['archive_sha256'],
            'source_bound_firmware_sha256':provenance['source_bound_firmware_sha256'],
            'serial_library_imported':False,'COM_opened':False,'UART_requests_sent':0,
            'hardware_accessed':False,'EDA_executed':False,'external_E2E':'UNMEASURED'},indent=2))

if __name__=='__main__':main()
