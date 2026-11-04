"""Actual small system, 16 input rasters: reproduce old stop / verify safe stop."""
import argparse
import copy
import csv
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
OLD_STOP = 'wait(unique_total==STRESS_ACCEPTED);@(negedge core_clk);scan_enable=0;wait_drain();'
SAFE_STOP = ('wait(unique_total==STRESS_ACCEPTED);\n'
             '        begin : complete_scan_before_stop\n'
             '            integer stop_after_sequence;\n'
             '            stop_after_sequence=scan_sequence;\n'
             '            wait(scan_sequence>stop_after_sequence);\n'
             '        end\n'
             '        @(negedge core_clk);scan_enable=0;wait_drain();')
OBSERVER = '''
    // Read-only diagnosis; no force, fault suppression or assertion change.
    always @(dut.output_video.fault_now)
        if(rst_n && dut.output_video.fault_now!=0)
            $display("TAIL_DIAG time=%0t fault=%h enable=%b active=%b request=%b unique=%0d scanseq=%0d",$time,dut.output_video.fault_now,dut.output_video.enable,dut.output_video.frame_active,dut.output_video.request_open,unique_total,scan_sequence);
    always @(negedge scan_enable)
        if(rst_n)$display("TAIL_HOST_STOP time=%0t unique=%0d scanseq=%0d input=%0d",$time,unique_total,scan_sequence,tx_frame);
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('old', 'safe'), required=True)
    args = parser.parse_args()
    source = HERE / 'run_fifo_system_a.py'
    spec = importlib.util.spec_from_file_location('tail_probe_bridge', source)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    evidence = bridge.Evidence()
    evidence.add(Path(__file__))
    evidence.add(source)
    contract = bridge.bind_contract('922bf8b196235d1b1ddc9c2e4575a0ae95c00583a55a230324761d796634edb2', evidence)
    family = bridge.family('sustained', evidence)
    work = HERE / ('stop-' + args.case + '-small-a')
    bridge.require(not work.exists(), 'fresh diagnostic case required')
    base, basepath, payloads, compiled, closure = bridge.inputs('sustained', 'small', work, contract, evidence)
    bench_name = 'tests/tb_hdmi_camera_fisheye_tile8df8_sustained.sv'
    bench_path = work / 'compiled-sources' / bench_name
    original = payloads[bench_path].decode()
    bridge.require(original.count(OLD_STOP) == 1, 'unique original stop stimulus required')
    # New diagnostic geometry strictly requires 16; other original checks stay.
    old_geometry = 'if(SIM_FRAMES!=(NATIVE?16:8)||'
    bridge.require(original.count(old_geometry) == 1, 'original exact frame-count check required')
    text = original.replace(old_geometry, 'if(SIM_FRAMES!=16||')
    if args.case == 'safe':
        text = text.replace(OLD_STOP, SAFE_STOP)
    bridge.require(text.count('endmodule') == 1, 'one original bench module required')
    text = text.replace('endmodule', OBSERVER + '\nendmodule')
    payloads[bench_path] = text.encode()
    timing_path = work / 'timing.vh'
    timing = payloads[timing_path]
    bridge.require(timing.count(b'SIM_FRAMES=8') == 1, 'small diagnostic input length anchor missing')
    payloads[timing_path] = timing.replace(b'SIM_FRAMES=8', b'SIM_FRAMES=16')
    fixture = copy.deepcopy(base['Fixture'])
    fixture['InputSourceFrames'] = 16
    fixture['FixtureSHA256']['timing.vh'] = bridge.digest(payloads[timing_path])
    work.mkdir()
    for path, data in payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        evidence.add(path, bridge.digest(data))
    result = {'Schema': 'tile8-original-scanner-tail-stop-diagnostic-v1', 'Passed': False,
              'Case': args.case, 'StartedUTC': bridge.utc(), 'ResearchOnly': True,
              'OriginalBadDoneCRCAndOwnershipAssertionsRetained': True,
              'NewTestGeometryStrictlyRequires16Inputs': True,
              'SourceContract': bridge.ref(bridge.CONTRACT), 'BaselineReceipt': bridge.ref(basepath),
              'InputSHA256': evidence.inputs, 'InputDrift': [], 'HardwareAccessed': False,
              'NativeEDAExecuted': False, 'Full1080SystemSimulation': False,
              'ProductionRTLModified': False}
    started = time.monotonic()
    try:
        from run_fill8_rowpipe_cache_sim import run_tool
        from simulation_tools import resolve_vivado_bin
        binary = resolve_vivado_bin(bridge.REPO)
        snapshot = 'tail_stop_' + args.case + '_small_a'
        deadline = started + 300
        for exe, argv, stage in (
                ('xvlog.bat', ['--sv', *map(str, compiled)], 'compile'),
                ('xelab.bat', [family.TOP, '-s', snapshot], 'elaborate'),
                ('xsim.bat', [snapshot, '-runall', '-log', 'simulation.log'], 'simulate')):
            bridge.require(not evidence.drift(), 'source drift before ' + stage)
            run_tool(binary, exe, argv, work, deadline, stage)
            bridge.require(not evidence.drift(), 'source drift after ' + stage)
        log = (work / 'simulation.log').read_text(errors='replace')
        if args.case == 'old':
            bridge.require('Fatal: bad scan completion outside deliberate small fault phase' in log and
                           'fault=07 enable=0 active=1' in log,
                           'old premature-stop fault07 was not actually reproduced')
            scans = list(csv.DictReader((work / 'scans.csv').open(newline='')))
            bridge.require({int(x['frame_id']) for x in scans} == {1, 2, 3, 4},
                           'old case did not complete four unique IDs before stop')
            result.update(Passed=True, ExpectedOriginalStopFailureActuallyReproduced=True,
                          DUTCorrectlyFaultedOnMidLeaseDisable=True, CompleteSystemPassed=False,
                          CompletedScanRows=scans)
        else:
            bridge.require(family.MARKER in log and 'Fatal:' not in log and '$finish called' in log,
                           'safe stop original assertions did not all complete')
            summary, rows = family.assess(work, fixture, 'directfill')
            result.update(Passed=True, ExpectedOriginalStopFailureActuallyReproduced=False,
                          CompleteSystemPassed=True, Summary=summary, Frames=rows,
                          ResetProbe=family.reset_probe(log, 'small'))
    except Exception as error:
        result['Error'] = type(error).__name__ + ': ' + str(error)
    result['InputDrift'] = evidence.drift()
    result['Passed'] = result['Passed'] and not result['InputDrift']
    result['ElapsedSeconds'] = time.monotonic() - started
    result['EndedUTC'] = bridge.utc()
    result['ArtifactsSHA256'] = {path.name: bridge.sha(path) for path in work.iterdir()
                                if path.is_file() and path.suffix in ('.log', '.csv', '.json')}
    bridge.write(work / 'simulation.json', result)
    print(json.dumps({k: result.get(k) for k in ('Passed', 'Case', 'Error', 'ElapsedSeconds',
                     'ExpectedOriginalStopFailureActuallyReproduced', 'CompleteSystemPassed')}))
    return 0 if result['Passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
