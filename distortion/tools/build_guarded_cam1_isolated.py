"""Bounded offline single-parameter CAM1 other-reset sink builder; no hardware path."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import math
import os
import re
import subprocess
import sys
import prepare_guarded_cam1_isolated as prepared

ROOT = prepared.ROOT
APPROVED = prepared.APPROVED
TARGET = prepared.TARGET
sha = prepared.sha
load = prepared.load


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def validate_pins(path):
    active = {}
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        fields = line.split('|')
        if len(fields) >= 7 and fields[4]:
            port = fields[4]
            if port in active or fields[6] != 'YES':
                raise ValueError('duplicate or inactive routed port: '+port)
            direction = ('input' if re.fullmatch(r'clk_27m|clk_p|clk_n|cam_pclk|cam_vsync|cam_href|cam_data\[\d+\]|uart_rxd', port)
                         else 'inout' if re.fullmatch(r'cam2_hold_rst_n|cam_rst_n|cam_scl|cam_sda|hd_scl|hd_sda|mem_dq\[\d+\]|mem_dqs(_n)?\[\d+\]', port)
                         else 'output')
            if fields[5] != direction:
                raise ValueError('routed direction differs: '+port)
            active[port] = fields[0]
    expected = load(ROOT/f'board/{TARGET}-pins.json')
    if (len(active) != 130 or len(set(active.values())) != 130 or active != expected or
            active.get('cam_data[5]') != 'Y21' or active.get('uart_rxd') != 'B24' or active.get('cam2_hold_rst_n') != 'Y20'):
        raise ValueError('CAM1 exact130 routed pin map/D5Y21/RXB24/other-resetY20 differs')
    return active


def validate_artifacts(work, before, simulation_path, simulation_sha):
    current = prepared.verify_clone()
    if current != before or sha(simulation_path) != simulation_sha:
        raise ValueError('CAM1/inherited sources or simulation evidence changed during build')
    prepared.validate_simulation(simulation_path)
    log = (work/'build-stdout.log').read_text(encoding='utf-8', errors='replace')
    stderr = (work/'build-stderr.log').read_text(encoding='utf-8', errors='replace')
    if (re.search(r'(?m)^\s*E:', log+'\n'+stderr) or not re.search(
            r'(?m)^Executing : gen_bit_stream -scbv \{High Voltage\} -unused_io_status UNUSED successfully\.\s*$', log)):
        raise ValueError('PDS did not finish named HighVoltage/UNUSED SRAM file generation')
    timing = work/'place_route'/f'{TARGET}_timing_summary_after_hold_fix.txt'
    pin_report = work/'place_route'/f'{TARGET}_prr.prt'
    bit = work/'generate_bitstream'/f'{TARGET}.sbit'
    if not timing.is_file() or not re.search(r'(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$', timing.read_text()):
        raise ValueError('final after_hold timing did not meet all constraints')
    validate_pins(pin_report)
    if not bit.is_file() or bit.stat().st_size == 0:
        raise ValueError('named nonempty CAM1 SRAM file missing')
    return {'Target': TARGET, 'Device': 'PG2L100H', 'Package': 'FBG676', 'SCBV': 'High Voltage',
            'UnusedIO': 'UNUSED', 'Bitstream': str(bit), 'SHA256': sha(bit).upper(),
            'TimingReport': str(timing), 'TimingSHA256': sha(timing).upper(),
            'PinReport': str(pin_report), 'PinReportSHA256': sha(pin_report).upper(),
            'SourceSHA256': before['SourceSHA256'], 'ReferenceSHA256': before['ReferenceSHA256'],
            'RawCaptureContract': before['RawCaptureContract'], 'GuardedControlContract': before['GuardedControlContract'],
            'CloneVerification': before['CloneVerification'],
            'OtherSensorResetTrialContract': before['OtherSensorResetTrialContract'], 'OtherSensorResetTrialVerification': before['OtherSensorResetTrialVerification'],
            'PreparedSourceManifestSHA256': sha(ROOT/f'board/{TARGET}-sources.json').upper(),
            'SimulationEvidence': str(simulation_path), 'SimulationEvidenceSHA256': simulation_sha.upper(),
            'ProcessExitCode': 0, 'HardwareAccessed': False, 'PhysicalEye': None,
            'CameraID': prepared.CAMERA_ID, 'ConnectorSlot': prepared.CAMERA_SLOT,
            'BuilderSHA256': sha(Path(__file__)).upper(),
            'Limits': 'CAM2 Y20 constant-low FPGA-side reset trial; no diagnosis or hardware fix inferred. Default68/full7FF0 mask, PLL and every readback unchanged; original129 pins retained and Y20 added. Physical reset independence and other-sensor inactivity unmeasured; sink applies only after configuration. Offline connector CAM1 candidate only. Boot disarmed. Lease uses nominal125MHz core cycles; core-clock loss pauses timers and UART. Inflight packets drain, failed partial raw retains lock. Finite host batch plus independent finally-heartbeat still required. No physical-eye, stereo synchronization, electrical, optics, calibrated temperature, unattended or hardware acceptance.'}


def stop_owned(child, work):
    if child.poll() is not None:
        return
    if os.name == 'nt':
        with (work/'owned-stop.log').open('xb') as output:
            subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),
                            '/PID', str(child.pid), '/T', '/F'], stdout=output,
                           stderr=subprocess.STDOUT, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        child.kill()
    child.wait(timeout=30)


def run_build(workdir, *, execute=False, simulation_evidence=None, pds_bin=None, timeout_seconds=1200):
    if type(execute) is not bool or type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 60 <= timeout_seconds <= 1800:
        raise ValueError('explicit execution flag and finite60..1800s build bound required')
    work = Path(workdir).resolve()
    if (not APPROVED.is_dir() or not work.is_relative_to(APPROVED.resolve()) or work == APPROVED.resolve()
            or not work.parent.is_dir() or work.exists()):
        raise ValueError('use fresh output below existing approved scratch; no overwrite')
    before = prepared.verify_clone()
    simulation_path = Path(simulation_evidence).resolve() if simulation_evidence else None
    if simulation_path:
        prepared.validate_simulation(simulation_path)
    if execute and simulation_path is None:
        raise ValueError('actual offline PDS requires fresh constant-sink actual-board lifecycle plus parameterized pipeline simulation evidence')
    pds = None
    if execute:
        config = load(ROOT.parent/'team-config.local.json') if (ROOT.parent/'team-config.local.json').is_file() else {}
        pds = Path(pds_bin or os.environ.get('FPGA_PDS_BIN') or config.get('pds_bin') or r'E:\Pango\PDS_2022.2-SP6.4\bin').resolve()
        if not (pds/'pds_shell.exe').is_file():
            raise ValueError('existing PDS pds_shell.exe required')
    work.mkdir()
    plan = {'Target': TARGET, 'ExecuteBuild': execute, 'HardwareAccessed': False,
            'Operation': 'offline_compile_route_sram_file_only', 'NoFlashOrProgrammingOperation': True,
            'SourceSHA256': before['SourceSHA256'], 'ReferenceSHA256': before['ReferenceSHA256'],
            'OutputDirectory': str(work), 'RawCaptureContract': before['RawCaptureContract'],
            'GuardedControlContract': before['GuardedControlContract'], 'OtherSensorResetTrialContract': before['OtherSensorResetTrialContract'],
            'SimulationEvidence': str(simulation_path) if simulation_path else None,
            'SimulationEvidenceSHA256': sha(simulation_path) if simulation_path else None,
            'BuilderSHA256': sha(Path(__file__)), 'PreparationHelperSHA256': sha(Path(prepared.__file__))}
    write_new(work/'plan.json', plan)
    if not execute:
        return plan
    result = {'Target': TARGET, 'Passed': False, 'HardwareAccessed': False,
              'StartedUtc': datetime.now(timezone.utc).isoformat(), 'OutputDirectory': str(work),
              'SourceSHA256': before['SourceSHA256'], 'ProcessExitCode': None, 'TimedOut': False}
    child = None
    try:
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        command = [str(pds/'pds_shell.exe'), '-file', str(ROOT/f'board/build-{TARGET}.tcl'),
                   '-work_dir', str(work), '-project_name', TARGET]
        result['Command'] = command
        with (work/'build-stdout.log').open('xb') as stdout, (work/'build-stderr.log').open('xb') as stderr:
            child = subprocess.Popen(command, cwd=str(work), stdout=stdout, stderr=stderr, **flags)
            result['OwnedPID'] = child.pid
            try:
                result['ProcessExitCode'] = child.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                result['TimedOut'] = True
                stop_owned(child, work)
                raise ValueError('owned offline PDS build exceeded finite bound')
        if type(result['ProcessExitCode']) is not int or result['ProcessExitCode'] != 0:
            raise ValueError('native PDS process exit code nonzero/unavailable')
        if (sha(Path(__file__)) != plan['BuilderSHA256'] or sha(Path(prepared.__file__)) != plan['PreparationHelperSHA256']):
            raise ValueError('offline builder/helper changed during build')
        manifest = validate_artifacts(work, before, simulation_path, plan['SimulationEvidenceSHA256'])
        write_new(work/'validated-build.json', manifest)
        result['Passed'] = True
        result['ValidatedBuild'] = str(work/'validated-build.json')
        result['ValidatedBuildSHA256'] = sha(work/'validated-build.json')
    except (Exception, KeyboardInterrupt) as error:
        result['Error'] = type(error).__name__+': '+str(error)
    finally:
        if child is not None and child.poll() is None:
            try:
                stop_owned(child, work)
            except Exception as error:
                result['CleanupError'] = str(error)
                result['Passed'] = False
        result['EndedUtc'] = datetime.now(timezone.utc).isoformat()
        write_new(work/'cam1-isolated-build-result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', required=True)
    parser.add_argument('--execute-build', action='store_true')
    parser.add_argument('--simulation-evidence')
    parser.add_argument('--pds-bin')
    parser.add_argument('--timeout-seconds', type=float, default=1200)
    args = parser.parse_args()
    try:
        result = run_build(args.workdir, execute=args.execute_build, simulation_evidence=args.simulation_evidence,
                           pds_bin=args.pds_bin, timeout_seconds=args.timeout_seconds)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if not args.execute_build or result.get('Passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
