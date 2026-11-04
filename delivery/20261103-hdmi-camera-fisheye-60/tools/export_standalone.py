"""Export a verified prepared candidate with all inputs and a standalone rebuilder."""
import argparse
import json
from pathlib import Path
import shutil

from standalone_rebuild import bound, digest, inspect_prepared, new_directory, require, verify_bundle

README = '''# FPGA fisheye candidate: standalone source bundle

This bundle contains the frozen prepared RTL, calibrated profile/ROM, DDR IP,
constraints, and build Tcl. It does not require the original Git checkout.
`candidate-plan.json` preserves the candidate's original source hashes and IDs.
`bundle-manifest.json` binds the export and independent rebuilding script.

The frozen `build.tcl` and some Verilog includes retain the original build root
for provenance. Relocate them before invoking PDS:

```powershell
python rebuild.py --verify-only
python rebuild.py --output D:/f60-rebuild
& '<PDS-install>/bin/pds_shell.exe' -file D:/f60-rebuild/build.tcl -work_dir D:/f60-rebuild -project_name hdmi_camera_fisheye_top
```

Use Python 3.9 or newer (standard library only). The output directory must be
new; choose a short path for Windows/PDS. The bundle itself can be moved before
running `rebuild.py`. All source and Tcl hashes are verified before relocation;
`rebuild-plan.json` records the resulting hashes and original candidate identity.

PDS and its device support/license must be installed separately. The candidate
has been built with PDS 2025.2 ADS build 211867; the frozen board-tested C source
lineage is recorded in the original manifest. A new implementation requires its
own timing, bitstream identity, and board validation. Export success establishes
source closure and relocation integrity; it does not establish FPGA timing or
60 new corrected frames per second. No hardware operation runs during export
or relocation.

This export contains the exact prepared constraints. Optional diagnostic FDCs
are included only if they were already part of that prepared candidate.
Rebuilding generates source inputs and Tcl; it does not run EDA automatically.
'''


def export(prepared, output):
    prepared = Path(prepared).resolve()
    plan, plan_bytes, tcl_bytes, original_root = inspect_prepared(prepared)
    output = new_directory(output, plan['source_files'])
    require(not output.is_relative_to(prepared), 'Export directory must be outside the prepared candidate')
    script = Path(__file__).with_name('standalone_rebuild.py').read_bytes()
    output.mkdir(parents=True)
    for name in plan['source_files']:
        destination = bound(output / 'compiled', name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bound(prepared / 'compiled', name), destination)
    (output / 'candidate-plan.json').write_bytes(plan_bytes)
    (output / 'build.tcl').write_bytes(tcl_bytes)
    (output / 'rebuild.py').write_bytes(script)
    (output / 'README.md').write_text(README, encoding='utf-8')
    names = ['candidate-plan.json', 'build.tcl', 'rebuild.py', 'README.md']
    record = {'schema': 'fisheye60-standalone-bundle-v1', 'source_identity': plan['source_identity'],
              'baseline_commit': plan['baseline_commit'], 'baseline_bitstream': plan['baseline_bitstream'],
              'build_id': plan['build_id'], 'profile_id': plan['profile_id'],
              'original_compiled_root': original_root, 'source_file_count': len(plan['source_files']),
              'bound_files': {n: digest((output / n).read_bytes()) for n in names},
              'eda_executed': False, 'hardware_accessed': False}
    (output / 'bundle-manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    verify_bundle(output)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    record = export(args.prepared, args.output)
    print(json.dumps({'exported': True, 'output': str(args.output.resolve()),
                      'source_files': record['source_file_count'], 'source_identity': record['source_identity']}))


if __name__ == '__main__':
    main()
