"""Small isolated build-gate tests; no PDS, JTAG or serial process is started."""
from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_probe_d5', ROOT/'tools/build_camera_isp_probe_d5.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


@pytest.fixture
def project(tmp_path, monkeypatch):
    original_root = ROOT
    source_names = set(build.ORIGINAL_SHA256)
    source_names |= {n.replace(build.ORIGINAL, build.TARGET) for n in source_names if build.ORIGINAL in n}
    for name in source_names:
        destination = tmp_path/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original_root/name, destination)
    scratch = tmp_path/'scratch'
    scratch.mkdir()
    pds = tmp_path/'pds'
    pds.mkdir()
    (pds/'pds_shell.exe').write_bytes(b'not executable; never started by these tests')
    monkeypatch.setattr(build, 'ROOT', tmp_path)
    monkeypatch.setattr(build, 'APPROVED', scratch)
    return tmp_path, scratch, pds


def artifacts(root, work):
    (work/'generate_bitstream').mkdir()
    (work/'place_route').mkdir()
    (work/'generate_bitstream'/f'{build.TARGET}.sbit').write_bytes(b'unit-test mock artifact')
    (work/'place_route'/f'{build.TARGET}_timing_summary_after_hold_fix.txt').write_text(
        'Design Summary : All Constraints Met.\n', encoding='utf-8')
    pins = build.load(root/f'board/{build.TARGET}-pins.json')
    (work/'place_route'/f'{build.TARGET}_prr.prt').write_text(
        ''.join(f'{pad}|mock|bank|type|{port}|input|YES\n' for port, pad in pins.items()), encoding='utf-8')


def fake_popen(monkeypatch, root, *, exitcode=0, mutate=None):
    calls = []
    class Child:
        pid = 12345
        def __init__(self, command, cwd, stdout, stderr, **flags):
            calls.append(command)
            self.returncode = None
            self.work = Path(cwd)
            artifacts(root, self.work)
            stdout.write(b'Executing : gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED successfully.\n')
            stdout.flush()
            if mutate:
                mutate(self.work)
        def wait(self, timeout=None):
            self.returncode = exitcode
            return exitcode
        def poll(self):
            return self.returncode
    monkeypatch.setattr(build.subprocess, 'Popen', Child)
    return calls


def test_exact_clone_and_16_sources(project):
    clone = build.verify_clone()
    assert len(clone['SourceSHA256']) == 16
    assert clone['UnchangedSharedDependencyCount'] == 11
    assert clone['OnlyPinChange']['to'] == 'AA23'


@pytest.mark.parametrize('name', [
    'board/camera_isp_probe_d5.v', 'board/camera_isp_probe_d5.fdc',
    'board/camera_isp_probe_d5-pins.json', 'board/build-camera_isp_probe_d5.tcl',
    'rtl/experimental/ov5640_cadence_trial_init.v',
])
def test_unapproved_clone_or_original_changes_rejected(project, name):
    root, _, _ = project
    with (root/name).open('ab') as stream:
        stream.write(b'\n// extra change\n')
    with pytest.raises(ValueError, match='changed|beyond'):
        build.verify_clone()


def test_fresh_mock_build_binds_final_artifacts(project, monkeypatch):
    root, scratch, pds = project
    calls = fake_popen(monkeypatch, root)
    result = build.run_build(scratch/'new', pds_bin=pds)
    assert result['Passed'] and result['ProcessExitCode'] == 0
    manifest = build.load(scratch/'new/validated-build.json')
    assert len(manifest['SourceSHA256']) == 16
    assert manifest['TimingReport'].endswith('_timing_summary_after_hold_fix.txt')
    assert manifest['HardwareAccessed'] is False
    assert len(calls) == 1 and calls[0][0].endswith('pds_shell.exe')
    assert not any('cfg_' in part for part in calls[0])


@pytest.mark.parametrize('failure', ['nonzero', 'timing', 'pin', 'source', 'stderr'])
def test_bad_result_never_creates_validated_manifest(project, monkeypatch, failure):
    root, scratch, pds = project
    def mutate(work):
        if failure == 'timing':
            (work/'place_route'/f'{build.TARGET}_timing_summary_after_hold_fix.txt').write_text('timing failed')
        elif failure == 'pin':
            p = work/'place_route'/f'{build.TARGET}_prr.prt'
            p.write_text(p.read_text().replace('AA23|', 'AA22|'))
        elif failure == 'source':
            with (root/f'board/{build.TARGET}.v').open('ab') as stream:
                stream.write(b'\n// changed while building\n')
        elif failure == 'stderr':
            (work/'build-stderr.log').write_text('E: mocked build error\n')
    fake_popen(monkeypatch, root, exitcode=2 if failure == 'nonzero' else 0, mutate=mutate)
    result = build.run_build(scratch/'bad', pds_bin=pds)
    assert not result['Passed']
    assert not (scratch/'bad/validated-build.json').exists()
    assert (scratch/'bad/probe-d5-build-result.json').exists()


def test_outside_or_existing_directory_rejected_before_popen(project, monkeypatch):
    _, scratch, pds = project
    monkeypatch.setattr(build.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not start PDS'))
    for work in (scratch, scratch.parent/'outside'):
        with pytest.raises(ValueError, match='fresh'):
            build.run_build(work, pds_bin=pds)


def test_timeout_stops_only_this_owned_handle(project, monkeypatch):
    _, scratch, pds = project
    owned = []
    stopped = []
    class Child:
        pid = 45678
        def __init__(self, *args, **kwargs):
            owned.append(self)
            self.returncode = None
        def wait(self, timeout=None):
            if self.returncode is None:
                raise subprocess.TimeoutExpired('mock owned PDS', timeout)
            return self.returncode
        def poll(self):
            return self.returncode
    def stop(child, work):
        stopped.append(child)
        child.returncode = -1
    monkeypatch.setattr(build.subprocess, 'Popen', Child)
    monkeypatch.setattr(build, 'stop_owned', stop)
    result = build.run_build(scratch/'timeout', pds_bin=pds, timeout_seconds=60)
    assert result['TimedOut'] and not result['Passed']
    assert stopped == owned and len(stopped) == 1
    assert not (scratch/'timeout/validated-build.json').exists()
