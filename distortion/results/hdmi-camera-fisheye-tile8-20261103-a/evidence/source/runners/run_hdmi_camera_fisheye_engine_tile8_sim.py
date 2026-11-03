"""Isolated tile8 sequencer/elastic-pixel/drain checks with the real dual writer."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import re
import subprocess
import time

from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8-20261103-a'
SELF = 'tools/run_hdmi_camera_fisheye_engine_tile8_sim.py'
SOURCES = ('tests/tb_hdmi_camera_fisheye_engine_tile8.sv',
           'rtl/experimental/hdmi_camera_fisheye_engine_tile8.v',
           'rtl/experimental/ddr_adaptive_result_writer_dualstripe.v')
HEADERS = ('rtl/video_crc32.vh',)
HELPERS = (SELF, 'tools/simulation_tools.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def tool(binary, name, args, work, deadline, stage):
    tokens = [str(binary / name), *args]
    shell = os.environ['ComSpec']
    require(all(not re.search(r'["\r\n&|<>^%!]', p) for p in [shell, *tokens]), 'unsafe simulator argument')
    line = '"' + shell + '" /d /s /c "' + ' '.join('"' + p + '"' for p in tokens) + '"'
    process = None
    with (work / (stage + '-stdout.log')).open('wb') as out, (work / (stage + '-stderr.log')).open('wb') as err:
        try:
            process = subprocess.Popen(line, cwd=work, stdout=out, stderr=err,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            code = process.wait(timeout=max(.01, deadline - time.monotonic()))
            require(code == 0, name + ' failed; see ' + str(work / (stage + '-stdout.log')))
        finally:
            if process is not None and process.poll() is None:
                result = subprocess.run([str(Path(os.environ['SystemRoot']) / 'System32/taskkill.exe'),
                                         '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
                (work / (stage + '-owned-stop.log')).write_bytes(result.stdout + result.stderr)
                process.wait(timeout=15)


def run(work, maximum=300):
    work = Path(work).resolve()
    require(work.parent == WORK.resolve() and not work.exists(), 'fresh direct tile8 child required')
    require(type(maximum) is int and 10 <= maximum <= 300, 'bounded unit simulation required')
    source_hashes = {name: sha(ROOT / name) for name in (*SOURCES, *HEADERS, *HELPERS)}
    work.mkdir()
    report = {'Schema': 'hdmi-camera-fisheye-engine-tile8-simulation-v1',
              'Passed': False, 'SourceSHA256': source_hashes, 'InputDrift': [],
              'HardwareAccessed': False, 'PDSAccessed': False,
              'ActualFisheyeCoreInstantiated': False, 'ActualCandidateWriterInstantiated': True,
              'StartedUTC': datetime.now(timezone.utc).isoformat(), 'Commands': []}
    try:
        paths, bindings = prepare_compile_sources(ROOT, SOURCES, HEADERS, work)
        report['RelocatedSources'] = bindings
        binary = resolve_vivado_bin(ROOT.parent)
        deadline = time.monotonic() + maximum
        for executable, argv, stage in (
            ('xvlog.bat', ['--sv', *map(str, paths)], 'compile'),
            ('xelab.bat', ['tb_hdmi_camera_fisheye_engine_tile8', '-s', 'engine_tile8'], 'elaborate'),
            ('xsim.bat', ['engine_tile8', '-runall', '-log', 'simulation.log'], 'simulate')):
            report['Commands'].append({'Stage': stage, 'Argv': [str(binary / executable), *argv], 'ReturnCode': None})
            tool(binary, executable, argv, work, deadline, stage)
            report['Commands'][-1]['ReturnCode'] = 0
        log = (work / 'simulation.log').read_text(encoding='utf-8', errors='replace')
        rows = re.findall(r'^PASS tile8 engine: frames=(\d+) coordinate_stalls=(\d+) writer_stalls=(\d+) reset_abort=1 overlap_rejected=1$', log, re.M)
        require(len(rows) == 1 and '$finish called' in log and not re.search(r'(?im)^\s*(?:fatal|error):', log), 'engine completion assertions absent')
        frames, coordinate, writer = map(int, rows[0])
        require(frames == 4 and coordinate > 0 and writer > 0, 'engine mode/backpressure coverage incomplete')
        report.update(Passed=True, FramesCompleted=frames, CoordinateStalls=coordinate,
                      WriterStalls=writer, IndependentCoordinateOracle=True,
                      RasterPixelsAndCRCChecked=True, FrameModeChangesWhileBusyExercised=True,
                      ResetAbortedFrameExercised=True, InvalidOverlappingBanksRejected=True)
    except (Exception, KeyboardInterrupt) as error:
        report['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        after = {name: sha(ROOT / name) for name in source_hashes}
        report['SourceSHA256After'] = after
        report['InputDrift'] = [name for name in source_hashes if source_hashes[name] != after[name]]
        if report['InputDrift']:
            report['Passed'] = False
        if report.get('RelocatedSources') is not None:
            try:
                verify_compile_sources(ROOT, SOURCES, HEADERS, work, report['RelocatedSources'])
            except ValueError as error:
                report.update(Passed=False, CompiledInputDrift=str(error))
        report['LogSHA256'] = {p.name: sha(p) for p in work.glob('*.log')}
        report['EndedUTC'] = datetime.now(timezone.utc).isoformat()
        report['Limits'] = 'Unit uses an independent elastic mock core to isolate tile/raster emission, masking, whole-pixel backpressure and writer raster CRC. Actual mapper/cache/system pixels require the separate real-system simulation.'
        (work / 'simulation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=int, default=300)
    args = parser.parse_args()
    value = run(args.workdir, args.maximum_seconds)
    print(json.dumps({key: value.get(key) for key in ('Passed', 'Error', 'FramesCompleted', 'InputDrift')}))
    return 0 if value['Passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
