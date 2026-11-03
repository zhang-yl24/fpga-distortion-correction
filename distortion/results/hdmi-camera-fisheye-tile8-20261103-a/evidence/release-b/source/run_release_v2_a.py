"""Release this proven r2 candidate to volatile SRAM, then measure corrected FPS.

Called only after the complete physical proof and the user's inherited SRAM
authorization. A concrete ready receipt is required so the user can be notified
before the actual programming step; no Flash write is provided.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[2]
sys.path[:0] = [str(REPO / 'distortion/tools'), str(REPO / '.venv/Lib/site-packages')]
import hdmi_camera_fisheye_tile8v2_bitstream as bit
import hdmi_camera_fisheye_tile8v2_program as program

_APPROVED_MANIFEST = None


def verify_revision(record=None):
    global _APPROVED_MANIFEST
    if record is not None:
        bit.require(_APPROVED_MANIFEST is None, 'revision authority already selected')
        _APPROVED_MANIFEST = dict(record)
    path = WORK / 'physical-release-provider-source-manifest-a.json'
    bit.require(_APPROVED_MANIFEST == bit.ref(path), 'approved revision manifest drift')
    manifest = bit.read(path)
    bit.require(manifest.get('Schema') == 'hdmi-camera-fisheye-tile8v2-provider-source-manifest-v1'
                and manifest.get('ProviderRevision') == 'tile8v2-bounded-b'
                and isinstance(manifest.get('InputSHA256'), dict) and manifest['InputSHA256'],
                'exact complete isolated revision input closure required')
    for name, digest in manifest['InputSHA256'].items():
        source = Path(name).absolute()
        bit.require(source == source.resolve() and source != path and
                    bit.build.local_io(source).is_file() and bit.sha(source) == digest,
                    'approved revision input changed: ' + name)


def note(stage, **values):
    value = {'Stage': stage, **values}
    print(json.dumps(value), flush=True)
    bit.write(WORK / ('release-v2-event-' + str(time.time_ns()) + '.json'), value)


def main():
    ready = bit.read(WORK / 'physical-to-release-v2-go-a.json')
    bit.require(ready.get('PriorWorkerEnded') is True and ready.get('PDriveReleased') is True
                and ready.get('UserAuthorizedVolatileSRAM') is True
                and ready.get('UserNotifiedBeforeExecution') is True,
                'completed physical handoff and inherited SRAM authorization required')
    bit.require(ready.get('ProviderRevision') == 'tile8v2-bounded-b', 'exact release provider revision required')
    verify_revision(ready['ProviderSourceManifest'])
    paths = {}
    for name in bit.FIELDS - {'Schema', 'Target'}:
        value = ready[name]
        path = Path(value['Path']).resolve()
        bit.require(value == bit.ref(path), 'release handoff input changed: ' + name)
        paths[name] = value
    request = {'Schema': bit.REQUEST_SCHEMA, 'Target': bit.TARGET, **paths}
    request_path = WORK / 'bit-request-v2-a.json'
    bit.write(request_path, request)
    bit.recipe(request_path, WORK / 'bit-v2-a', maximum=3600)
    owned_alias = False
    try:
        bit.require(not Path('P:/').exists(), 'physical worker must release P: before bit generation')
        result = subprocess.run(['subst.exe', 'P:', str(REPO)], capture_output=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        bit.require(result.returncode == 0 and os.path.samefile('P:/', REPO), 'owned P: alias failed')
        owned_alias = True
        note('bit-prepare', Started=True, MaximumSeconds=3600, HardwareAccessed=False)
        bit.prepare(request_path, WORK / 'bit-v2-a', maximum=3600)
        note('bit-execute', Started=True)
        verify_revision()
        generated = bit.execute(WORK / 'bit-v2-a')
        bit.require(generated.get('Verified') is True, 'actual bit generation failed')
        verified = bit.verify(WORK / 'bit-v2-a')
        bit.require(verified.get('Verified') is True, 'actual bit verification failed')
        note('bit-verified', Bitstream=verified['Bitstream'], HardwareAccessed=False)
        plan = program.prepare(WORK / 'bit-v2-a', WORK / 'program-v2-a')
        bit.require(plan['Operation'] == 'volatile_sram_only' and plan['FlashWritten'] is False,
                    'only volatile SRAM authorized')
        note('program', Started=True, FlashWritten=False)
        verify_revision()
        receipt = program.execute(WORK / 'program-v2-a/plan.json', board_powered=True,
                                  user_notified=True, timeout=90)
        bit.require(receipt['Passed'] is True and receipt['DoneConfirmed'] is True
                    and receipt['ExpectedDeviceAndIDConfirmed'] is True
                    and receipt['FlashWritten'] is False and receipt['CleanupErrors'] == [],
                    'actual SRAM programming unsuccessful')
        note('program', Passed=True, Bitstream=receipt['Bitstream'], FlashWritten=False)
        time.sleep(15)
        import measure_hdmi_fisheye_fps as fps
        measured = fps.measure(WORK / 'fps-corrected-v2-a', WORK / 'program-v2-a/receipt.json',
                               seconds=30, port='COM7')
        bit.require(measured['passed'] is True, 'corrected FPS measurement failed')
        note('fps-corrected', Passed=True, Summary=measured['nominal_clock_summary'],
             Host=measured['independent_host_summary'])
    finally:
        if owned_alias:
            bit.require(os.path.samefile('P:/', REPO), 'owned P: alias changed before cleanup')
            subprocess.run(['subst.exe', 'P:', '/D'], check=True, capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


if __name__ == '__main__':
    main()
