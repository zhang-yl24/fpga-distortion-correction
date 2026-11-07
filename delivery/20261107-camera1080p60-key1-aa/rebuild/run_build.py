"""Explicit user-operated offline PDS stage entry point; never programs a board."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys
from verify_sources import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['map', 'place', 'route', 'sta', 'bitgen'])
    parser.add_argument('--pds', required=True, type=Path, help='Installed licensed pds_shell executable')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--input-adf', type=Path, help='Newly generated matching stage checkpoint; mandatory after map')
    args = parser.parse_args()
    root = args.root.resolve()
    missing, errors = check(root)
    if missing or errors:
        for name in missing:
            print('MISSING ' + name)
        for error in errors:
            print('ERROR ' + error)
        print('STOP: incomplete source closure. No EDA launched.')
        return 2
    tool = Path(shutil.which(str(args.pds)) or args.pds).resolve()
    if not tool.is_file():
        parser.error('pds_shell executable does not exist')
    checkpoint = None
    if args.stage != 'map':
        if args.input_adf is None:
            parser.error('--input-adf is required: place uses *_map.adf; route *_plc.adf; STA/bitgen final optimized *_pnr.adf')
        checkpoint = args.input_adf.resolve()
        if not checkpoint.is_file() or checkpoint.suffix.lower() != '.adf':
            parser.error('input checkpoint must be an existing ADF from this new build')
    out = root / 'build-repro' / args.stage
    out.parent.mkdir(exist_ok=True)
    # Never overwrite or silently resume an existing stage directory.
    out.mkdir(exist_ok=False)
    env = os.environ.copy()
    env['REPRO_ROOT'] = str(root)
    if checkpoint:
        env['REPRO_INPUT_ADF'] = str(checkpoint)
    else:
        env.pop('REPRO_INPUT_ADF', None)
    tcl = Path(__file__).resolve().parent / (args.stage + '.tcl')
    command = [str(tool), '-file', str(tcl), '-work_dir', str(out), '-project_name', 'aa_' + args.stage]
    with (out / 'console.log').open('wb') as log:
        result = subprocess.run(command, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT)
    print('Stage exit code:', result.returncode)
    print('Review generated reports and checkpoint identity before the next stage; exit zero is not timing signoff.')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
