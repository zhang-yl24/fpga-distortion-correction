"""Real final-commit/reset/fault and chosen-way CHECK boundary simulations."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / 'distortion'
sys.path.insert(0, str(ROOT / 'tools'))
from run_fill8_rowpipe_cache_sim import run_tool
from simulation_tools import resolve_vivado_bin

SOURCE = HERE / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v'
PIN = '745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.parent == HERE and output.name.startswith('boundary-') and not output.exists(), 'fresh boundary output required')
    require(sha(SOURCE) == PIN, 'RTL source differs')
    output.mkdir()
    jobs = (('commit', HERE / 'tests/tb_assoc2_commit_collision_a.sv', 'tb_directfill_tagpipe_commit_collision',
             'PASS DIRECTFILL PEER real final-commit/fault/reset collisions'),
            ('check', HERE / 'tests/tb_assoc2_check_fault_a.sv', 'tb_assoc2_check_fault_a',
             'PASS ASSOC2 CHECK way1 unowned R fault boundary'))
    files = [SOURCE, Path(__file__), ROOT / 'tools/run_fill8_rowpipe_cache_sim.py', ROOT / 'tools/simulation_tools.py']
    files.extend(job[1] for job in jobs)
    watched = {str(p.resolve()): sha(p) for p in files}
    result = dict(Schema='tile8-assoc2-tagpipe-independent-boundary-simulation-v1', Passed=False,
                  StartedUTC=datetime.now(timezone.utc).isoformat(), SourceSHA256=watched,
                  HDLSimulationExecuted=False, PDSAccessed=False, HardwareAccessed=False,
                  NativeRAMMappingOrTimingAccepted=False, FullFrameSimulated=False)
    started = time.monotonic()
    try:
        binary = resolve_vivado_bin(ROOT.parent)
        result['VivadoBin'] = str(binary)
        deadline = started + 240
        result['HDLSimulationExecuted'] = True
        for name, bench, top, marker in jobs:
            work = output / name
            work.mkdir()
            run_tool(binary, 'xvlog.bat', ['--sv', str(SOURCE), str(bench)], work, deadline, 'compile')
            run_tool(binary, 'xelab.bat', [top, '-s', 'boundary_tb'], work, deadline, 'elaborate')
            run_tool(binary, 'xsim.bat', ['boundary_tb', '-runall', '-log', 'simulation.log'], work, deadline, 'simulate')
            log = (work / 'simulation.log').read_text(errors='replace')
            require(marker in log and '$finish called' in log and not re.search(r'(?im)^\s*(fatal|error):', log), name + ' boundary did not complete')
        commit = json.loads((output / 'commit/peer-commit-summary.json').read_text())
        expected = dict(Passed=True, IndexBits=10, Cases=4, SuccessfulCommonResetRecoveries=4,
                        IndependentRAMPixelsChecked=864, NinthRAndLastCommitCollision=True,
                        MalformedFinalRID=True, MissingFinalRLAST=True,
                        ResetBeforeFinalRAMCommit=True, FaultQuarantineChecked=True)
        require(commit == expected, 'original four independent collision cases changed')
        require((output / 'commit/peer-commit-cases.csv').read_text().splitlines()[1:] == [
            '0,ninth_R_vs_last_commit,128,4,0', '1,malformed_final_R,112,3,0',
            '2,malformed_final_R,112,3,0', '3,common_reset_vs_last_commit,0,0,0'], 'collision raw case rows differ')
        check = json.loads((output / 'check/check-way1-fault-summary.json').read_text())
        require(check == dict(Passed=True, IndexBits=10, NormalIndependentPixelOutputs=2,
                             UnownedRAtWay1HitCHECK=True, ChosenWay1Invalidated=True,
                             OtherWay0Preserved=True, StickyQuarantineCycles=20, HierarchyForced=False),
                'CHECK chosen-way fault case missing')
        result.update(Passed=True, CommitBoundary=commit, CheckWay1FaultBoundary=check)
    except BaseException as error:
        result['Error'] = type(error).__name__ + ': ' + str(error)
    result['InputDrift'] = [n for n, h in watched.items() if sha(n) != h]
    result['Passed'] = result['Passed'] and not result['InputDrift']
    result['ElapsedSeconds'] = round(time.monotonic() - started, 3)
    result['EndedUTC'] = datetime.now(timezone.utc).isoformat()
    result['ArtifactsSHA256'] = {p.relative_to(output).as_posix(): sha(p) for p in output.rglob('*')
                               if p.is_file() and p.suffix in ('.log', '.json', '.csv', '.txt')}
    with (output / 'simulation.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: result.get(k) for k in ('Passed', 'Error', 'ElapsedSeconds', 'InputDrift', 'CommitBoundary', 'CheckWay1FaultBoundary')}))
    raise SystemExit(0 if result['Passed'] else 1)


if __name__ == '__main__':
    main()
