"""Check fixed measurement modes and retained demo switching using Vivado."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(work, vivado):
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    files = [ROOT / 'rtl/frame_ab_control.v', ROOT / 'tests/tb_mode_control.sv']
    result = {'passed': False, 'hardware_accessed': False,
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    try:
        for stage, tool, args in [('compile', 'xvlog.bat', ['--sv', *map(str, files)]),
                                  ('elaborate', 'xelab.bat', ['tb_mode_control', '-s', 'modes']),
                                  ('simulate', 'xsim.bat', ['modes', '-runall'])]:
            p = subprocess.run([str(vivado / tool), *args], cwd=work, capture_output=True, timeout=120)
            output = p.stdout + p.stderr
            (work / (stage + '.log')).write_bytes(output)
            if p.returncode:
                raise RuntimeError(stage + ' failed')
        if b'PASS MODE_CONTROL' not in output:
            raise RuntimeError('Mode-control PASS missing')
        result['passed'] = True
    except Exception as exc:
        result['error'] = str(exc)
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--vivado-bin', type=Path, default=Path(os.environ.get('FPGA_VIVADO_BIN', 'D:/Vicado/Vivado/2017.4/bin')))
    args = p.parse_args()
    raise SystemExit(run(args.work, args.vivado_bin))
