"""Offline-only, bounded PDS build of the exact AA23 camera ISP probe clone.

This entry point has no serial, JTAG, configuration server or programming path.
Original probe sources and all other targets remain immutable. New build files
are exclusive children of the previously approved offline scratch directory.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT/'build/offline-20261024'
ORIGINAL = 'camera_isp_probe'
TARGET = 'camera_isp_probe_d5'
ORIGINAL_SHA256 = {
    'rtl/camera_preview.v': '9cc0a8344a3245f2c986d6ac7bb3abea721fbb04de4404c2025b1db361a17681',
    'rtl/dvp_rgb565_capture.v': 'fffb56b608c0cfcb641da389df45e96acac1967ae075c55c9f6e9c2f1ba9a9e1',
    'rtl/reg16_i2c.v': '7db5335dee7d64eddf3905008a1cd64262889d0a9ebef63c74d4612d70a5a580',
    'rtl/uart_tx.v': '0a691c35b88d4305d9c74c4acd8676defa09c8c5aae7d7ee653c561f40b49d2b',
    'rtl/experimental/ov5640_cadence_trial_init.v': '66e2a8236ca8a5d7bb56e46893cf640d3aa9e8b2c4f4b9119340cabfbb153ec7',
    'rtl/experimental/ov5640_state_scan.v': '14d668cf12e2b43199c1692f05bbd0d0ef8ce220a2360118539f11431729dd24',
    'board/hdmi_tx_init.v': '184883cd018e7d6ccc8937e9a23bc208fdc5699b9040e3fdd70c6cf3a52f165c',
    'rtl/video_pattern.v': '299e59ec4c3168a282bf9d521189dfc405ff889e65825846084962826c149aa9',
    'board/camera_isp_probe.v': '52a77abd41f5b51e8ca270d19fe91321df1f23d6bc5e0c810e7cdbaa8fe0a760',
    'board/bringup_pll.v': 'dcf95900356fea020ab2b6a43cf2c61ba08ab14d024be3f8fff5167eaa0dc2e0',
    'board/camera_isp_probe.fdc': '85827f8f6f755b089f3df83d877eba18403e0545716991c174cf11a79d60727f',
    'board/camera_isp_probe-pins.json': 'b1bbd75999fbdae4a3a230528246e3dbb9ddcdf162f283109836bd0a33cfb58e',
    'board/build-camera_isp_probe.tcl': '1535696812e707d42d4d77a14c16e1be81e9d84711466ac6477737542e62af2c',
    'board/ov5640_cadence_trial_commands.vh': '53428872aa14e6120eed93d876c889ef5155b3c196c014db77c4578b2bd50674',
    'board/ms7210_commands.vh': 'd542c30438a2243275c9a48f3b8db742d585a358d3b6da685373c8808dbcee64',
    'board/camera_isp_probe-sources.json': '201e0d6f5990da7b555670b43e604c97ced41721f256df177d116ee2b5156fda',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def verify_clone():
    """Pin all 16 old inputs, then allow exactly the five prescribed copies."""
    for name, expected in ORIGINAL_SHA256.items():
        if sha(ROOT/name) != expected:
            raise ValueError('immutable original probe dependency changed: '+name)
    old_list = load(ROOT/f'board/{ORIGINAL}-sources.json')
    new_list = load(ROOT/f'board/{TARGET}-sources.json')
    expected_list = [name.replace(ORIGINAL, TARGET) for name in old_list]
    if (not isinstance(old_list, list) or len(old_list) != 16 or
            set(old_list) != set(ORIGINAL_SHA256) or new_list != expected_list):
        raise ValueError('clone must preserve the exact ordered 16-file dependency closure')
    own = (f'board/{ORIGINAL}.v', f'board/{ORIGINAL}.fdc',
           f'board/{ORIGINAL}-pins.json', f'board/{ORIGINAL}-sources.json',
           f'board/build-{ORIGINAL}.tcl')
    for old_name in own:
        original = (ROOT/old_name).read_bytes()
        if old_name.endswith('.v'):
            expected = original.replace(b'module camera_isp_probe(', b'module camera_isp_probe_d5(', 1)
        elif old_name.endswith('.fdc'):
            expected = original.replace(
                b'define_attribute {p:cam_data[5]} {PAP_IO_LOC} {AA22}',
                b'define_attribute {p:cam_data[5]} {PAP_IO_LOC} {AA23}', 1)
        elif old_name.endswith('-pins.json'):
            expected = original.replace(b'"cam_data[5]": "AA22"', b'"cam_data[5]": "AA23"', 1)
        else:
            expected = original.replace(ORIGINAL.encode(), TARGET.encode())
        new_name = old_name.replace(ORIGINAL, TARGET)
        if (ROOT/new_name).read_bytes() != expected:
            raise ValueError('clone contains changes beyond module/own paths/D5 AA23: '+new_name)
    pins = load(ROOT/f'board/{TARGET}-pins.json')
    if pins.get('cam_data[5]') != 'AA23' or len(pins) != len(set(pins.values())):
        raise ValueError('clone D5 or unique board-side pin mapping differs')
    sources = {name: sha(ROOT/name) for name in new_list}
    return {'kind': 'exact_original_probe_clone_module_and_D5_only',
            'OriginalTarget': ORIGINAL, 'OriginalSourceSHA256': dict(ORIGINAL_SHA256),
            'SourceSHA256': sources, 'UnchangedSharedDependencyCount': 11,
            'OnlyPinChange': {'port': 'cam_data[5]', 'from': 'AA22', 'to': 'AA23'},
            'CameraInitializationWritesRegisters': True, 'HDMIInitializationWritesRegisters': True,
            'ReadoutStartsAfterCameraReady': True,
            'Limits': 'Same initializer and scanner as original probe. ID 0x5640 is a model ID, not a unique serial. No native pixels, temperature or physical eye synchronization is certified.'}


def routed_pins(path):
    active = {}
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        fields = line.split('|')
        if len(fields) >= 7 and fields[4]:
            if fields[6] != 'YES' or fields[4] in active:
                raise ValueError('duplicate or inactive routed port: '+fields[4])
            active[fields[4]] = fields[0]
    if len(active.values()) != len(set(active.values())):
        raise ValueError('routed board-side pin collision')
    return active


def validate_artifacts(work, before, original_before):
    current = verify_clone()
    if current['SourceSHA256'] != before or current['OriginalSourceSHA256'] != original_before:
        raise ValueError('clone/original sources changed during the PDS build')
    log = (work/'build-stdout.log').read_text(encoding='utf-8', errors='replace')
    stderr = (work/'build-stderr.log').read_text(encoding='utf-8', errors='replace')
    if (re.search(r'(?m)^\s*E:', log+'\n'+stderr) or
            not re.search(r'(?m)^Executing : gen_bit_stream\b[^\r\n]* successfully\.\s*$', log)):
        raise ValueError('PDS did not complete bitstream generation without E: diagnostics')
    bit = work/'generate_bitstream'/f'{TARGET}.sbit'
    timing = work/'place_route'/f'{TARGET}_timing_summary_after_hold_fix.txt'
    report = work/'place_route'/f'{TARGET}_prr.prt'
    if not bit.is_file() or bit.stat().st_size == 0:
        raise ValueError('named nonempty clone bitstream is missing')
    if not timing.is_file() or not re.search(
            r'(?m)^\s*(?:Design Summary\s*:\s*)?All Constraints Met\.\s*$',
            timing.read_text(encoding='utf-8', errors='replace')):
        raise ValueError('final after-hold timing is missing or constraints are not met')
    pins = load(ROOT/f'board/{TARGET}-pins.json')
    if routed_pins(report) != pins:
        raise ValueError('all routed active ports must exactly match the clone pin map')
    return {'Target': TARGET, 'Device': 'PG2L100H', 'Package': 'FBG676',
            'SCBV': 'High Voltage', 'UnusedIO': 'UNUSED', 'Bitstream': str(bit),
            'SHA256': sha(bit), 'TimingReport': str(timing), 'TimingSHA256': sha(timing),
            'RoutedPinReport': str(report), 'RoutedPinSHA256': sha(report),
            'SourceSHA256': before, 'CloneVerification': current,
            'HardwareAccessed': False, 'ProcessExitCode': 0,
            'BuilderSHA256': sha(Path(__file__)),
            'Limits': 'Offline-only AA23 electrical CAM2 ISP probe clone. No hardware download, physical sensor/register observation, temperature or optical acceptance has occurred.'}


def resolve_pds_bin(value=None):
    if value is None:
        config_path = ROOT.parent/'team-config.local.json'
        config = load(config_path) if config_path.is_file() else {}
        value = os.environ.get('FPGA_PDS_BIN') or config.get('pds_bin') or r'E:\Pango\PDS_2022.2-SP6.4\bin'
    path = Path(value).resolve()
    if not (path/'pds_shell.exe').is_file():
        raise ValueError('the existing PDS bin must contain pds_shell.exe')
    return path


def stop_owned(child, work):
    """Only the still-running process handle from this invocation is eligible."""
    if child.poll() is not None:
        return
    if os.name == 'nt':
        with (work/'owned-stop.log').open('xb') as output:
            subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),
                            '/PID', str(child.pid), '/T', '/F'],
                           stdout=output, stderr=subprocess.STDOUT, check=False,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        child.kill()
    child.wait(timeout=30)


def run_build(workdir, *, pds_bin=None, timeout_seconds=1200):
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 60 <= timeout_seconds <= 1800):
        raise ValueError('offline build bound must be finite within 60..1800 seconds')
    approved = APPROVED.resolve()
    work = Path(workdir).resolve()
    if (not approved.is_dir() or work == approved or not work.is_relative_to(approved)
            or not work.parent.is_dir() or work.exists()):
        raise ValueError('use a fresh direct/descendant directory below existing approved scratch; no overwrite')
    clone = verify_clone()
    pds = resolve_pds_bin(pds_bin)
    work.mkdir()
    result = {'Target': TARGET, 'Passed': False, 'HardwareAccessed': False,
              'StartedUtc': datetime.now(timezone.utc).isoformat(), 'OutputDirectory': str(work),
              'TimeoutSeconds': timeout_seconds, 'SourceSHA256': clone['SourceSHA256'],
              'OriginalSourceSHA256': clone['OriginalSourceSHA256'],
              'BuilderSHA256': sha(Path(__file__)), 'ProcessExitCode': None, 'TimedOut': False}
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
                raise ValueError('owned offline PDS build exceeded its bound; no candidate validated')
        if type(result['ProcessExitCode']) is not int or result['ProcessExitCode'] != 0:
            raise ValueError('PDS returned a nonzero/unavailable native process exit code')
        manifest = validate_artifacts(work, clone['SourceSHA256'], clone['OriginalSourceSHA256'])
        write_new(work/'validated-build.json', manifest)
        result['Passed'] = True
        result['ValidatedBuild'] = str(work/'validated-build.json')
        result['ValidatedBuildSHA256'] = sha(work/'validated-build.json')
    except Exception as error:
        result['Error'] = str(error)
    finally:
        if child is not None and child.poll() is None:
            try:
                stop_owned(child, work)
            except Exception as error:
                result['CleanupError'] = str(error)
                result['Passed'] = False
        result['SourcesUnchangedAfterBuild'] = all(sha(ROOT/n) == h for n, h in clone['SourceSHA256'].items())
        result['OriginalSourcesUnchangedAfterBuild'] = all(sha(ROOT/n) == h for n, h in clone['OriginalSourceSHA256'].items())
        result['EndedUtc'] = datetime.now(timezone.utc).isoformat()
        write_new(work/'probe-d5-build-result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir')
    parser.add_argument('--pds-bin')
    parser.add_argument('--timeout-seconds', type=float, default=1200)
    parser.add_argument('--check-clone-only', action='store_true')
    args = parser.parse_args()
    if args.check_clone_only:
        print(json.dumps(verify_clone(), indent=2))
        return 0
    if not args.workdir:
        parser.error('--workdir below approved offline scratch is required')
    try:
        result = run_build(args.workdir, pds_bin=args.pds_bin, timeout_seconds=args.timeout_seconds)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result['Passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
