"""Check the lane output FIFO with controlled producer and consumer boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--vivado-bin', type=Path, default=Path('D:/Vicado/Vivado/2017.4/bin'))
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    names = ['rtl/hdmi_camera_fisheye_lane.v', 'tests/lane_output_fifo.sv']
    hashes = {}
    for name in names:
        data = (package/name).read_bytes()
        (work/Path(name).name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    report = {'passed': False, 'hardware_accessed': False, 'source_sha256': hashes,
              'scope': 'Actual lane RTL with core/writer doubles; real datapath verified separately.', 'commands': []}
    try:
        commands = [['xvlog', '--sv', *[Path(n).name for n in names]],
                    ['xelab', 'tb_lane_output_fifo', '-s', 'lane_fifo'], ['xsim', 'lane_fifo', '-runall']]
        for command in commands:
            argv = [str(args.vivado_bin/(command[0]+'.bat')), *command[1:]]
            result = subprocess.run(argv, cwd=work, capture_output=True, text=True, errors='replace', timeout=120)
            output = result.stdout + result.stderr
            (work/(command[0]+'.log')).write_text(output, encoding='utf-8')
            report['commands'].append({'command': argv, 'returncode': result.returncode})
            if result.returncode or re.search(r'(?im)^\s*(fatal|error)(?:\s|:|\[)', output):
                raise RuntimeError(command[0]+': '+output[-4000:])
        if 'PASS LANE FIFO2' not in output or 'PASS LANE LAUNCH' not in output:
            raise RuntimeError('Completion marker missing')
        if hashes != {name: hashlib.sha256((package/name).read_bytes()).hexdigest() for name in names}:
            raise RuntimeError('Sources changed after snapshot')
        report['passed'] = True
        report['summary'] = [line for line in output.splitlines() if line.startswith(('PASS LANE FIFO2', 'PASS LANE LAUNCH'))]
        print(json.dumps(report, indent=2))
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (work/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
