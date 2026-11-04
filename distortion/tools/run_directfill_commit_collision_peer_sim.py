"""Small independent XSim peer test; never PDS, JTAG, UART or old-output writes."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import time

from run_fill8_rowpipe_cache_sim import run_tool
from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df9-20261103-a'
SOURCE = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
SOURCE_SHA256 = 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e'
BENCH = ROOT / 'tests/tb_directfill_commit_collision_peer.sv'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def run(output, maximum):
    output = Path(output).resolve()
    require(output.parent == WORK and output.name.startswith('cache-commit-collision-') and
            not output.exists() and 30 <= maximum <= 240, 'fresh bounded peer collision output required')
    require(sha(SOURCE) == SOURCE_SHA256, 'frozen direct-fill cache source drift')
    output.mkdir()
    watched = {str(path.resolve()): sha(path) for path in (
        SOURCE, BENCH, Path(__file__), ROOT / 'tools/run_fill8_rowpipe_cache_sim.py',
        ROOT / 'tools/simulation_tools.py')}
    value = {'Schema': 'tile8-directfill-independent-peer-commit-collision-v1', 'Passed': False,
             'StartedUTC': datetime.now(timezone.utc).isoformat(), 'SourceSHA256': watched,
             'HDLSimulationExecuted': False, 'PDSAccessed': False, 'HardwareAccessed': False,
             'OldUnitReceiptModified': False, 'NativeRAMMappingOrTimingAccepted': False}
    started = time.monotonic()
    try:
        binary = resolve_vivado_bin(ROOT.parent)
        value['VivadoBin'] = str(binary)
        deadline = started + maximum
        value['HDLSimulationExecuted'] = True
        run_tool(binary, 'xvlog.bat', ['--sv', str(SOURCE), str(BENCH)], output, deadline, 'compile')
        run_tool(binary, 'xelab.bat', ['tb_directfill_commit_collision_peer', '-s', 'peer_collision'],
                 output, deadline, 'elaborate')
        run_tool(binary, 'xsim.bat', ['peer_collision', '-runall', '-log', 'simulation.log'],
                 output, deadline, 'simulate')
        log = (output / 'simulation.log').read_text(errors='replace')
        require('PASS DIRECTFILL PEER real final-commit/fault/reset collisions' in log and
                '$finish called' in log and not re.search(r'(?im)^\s*(fatal|error):', log),
                'real peer simulation failed or did not complete')
        summary = json.loads((output / 'peer-commit-summary.json').read_text())
        expected = {'Passed': True, 'IndexBits': 9, 'Cases': 4, 'SuccessfulCommonResetRecoveries': 4,
                    'IndependentRAMPixelsChecked': 864, 'NinthRAndLastCommitCollision': True,
                    'MalformedFinalRID': True, 'MissingFinalRLAST': True,
                    'ResetBeforeFinalRAMCommit': True, 'FaultQuarantineChecked': True}
        require(summary == expected, 'complete independent collision coverage required')
        lines = (output / 'peer-commit-cases.csv').read_text().splitlines()
        require(len(lines) == 5 and lines[1:] == [
            '0,ninth_R_vs_last_commit,128,4,0', '1,malformed_final_R,112,3,0',
            '2,malformed_final_R,112,3,0', '3,common_reset_vs_last_commit,0,0,0'],
            'actual collision/fault/valid trace differs')
        value.update(Summary=summary, Passed=True)
    except BaseException as error:
        value['Error'] = type(error).__name__ + ': ' + str(error)
    value['InputDrift'] = [name for name, digest in watched.items() if sha(Path(name)) != digest]
    value['Passed'] = value['Passed'] and not value['InputDrift']
    value['ElapsedSeconds'] = round(time.monotonic() - started, 3)
    value['EndedUTC'] = datetime.now(timezone.utc).isoformat()
    value['ArtifactsSHA256'] = {path.relative_to(output).as_posix(): sha(path)
                               for path in output.rglob('*') if path.is_file() and path.suffix in ('.log', '.json', '.csv', '.txt')}
    with (output / 'simulation.json').open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=int, default=180)
    args = parser.parse_args()
    result = run(args.output, args.maximum_seconds)
    print(json.dumps({key: result.get(key) for key in ('Passed', 'Error', 'ElapsedSeconds', 'InputDrift', 'Summary')}))
    raise SystemExit(0 if result['Passed'] else 1)
