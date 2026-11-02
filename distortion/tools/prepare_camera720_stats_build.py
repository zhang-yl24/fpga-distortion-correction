"""Bounded native-build preparation for the isolated calibrated statistics top.

Only CPU source preparation runs here. The caller separately executes the new
runner; no physical acceptance, bitstream or hardware operation is inherited.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

import prepare_camera720_calibrated_stats as source

SELF = Path(__file__).resolve()
PROJECT, WORK, TARGET = source.PROJECT, source.WORK, source.TARGET
RUNNER = PROJECT/'tools/run_camera720_stats_build.py'
CLEANUP = PROJECT/'tools/run_camera_vga_output_diagnostic.py'
SCHEMA = 'camera720-calibrated-stats-build-preparation-v1'
SOURCE_SHA = 'ea8884369b13de4db4b40fb1854932ef3d0b61970d3cb47d13bdf88e3b0c481e'
SOURCE_PRODUCER_SHA = '54c8aff1e4afb870e3fbb1a24b02a8c715671c07ea495000343451082691b5f8'
HEADER = 'board/camera720-current-lens.vh'
# The header and profile have separate identities; the header is generated code.
HEADER_SHA = '01c797c6f5e327dae6977c8738ea472551f2f715b415784eaa52ffd2019b9e4a'
PROFILE_SHA = 'f79c44d9bdeb5b114441e53d172d2b22667ba415717dc3a49a4b0a73e15200e8'
STAGES = ['Compile', 'Synthesize', 'Device Map', 'Place', 'Route', 'Route Optimize', 'Report Timing']
require, sha, ref, read, encoded = source.require, source.sha, source.ref, source.read, source.encoded


def work_path(value):
    p = Path(value).absolute()
    require(p == p.resolve() and p.parent == WORK.resolve()
            and re.fullmatch('[A-Za-z0-9_-]+', p.name), 'fresh direct statistics build directory required')
    return p


def fixed_source_contract(plan, manifest):
    require(manifest['Target'] == TARGET and manifest['SourceSHA256'][HEADER] == HEADER_SHA
            and manifest['ProfileSHA256'] == PROFILE_SHA,
            'current measured profile/header differs')
    require(manifest['SourceSHA256'][source.STATS] == source.STATS_SHA
            and manifest['AddedSources'] == [source.STATS, source.UART]
            and manifest['CounterDomain'] == 'core_clk' and manifest['CounterReset'] == 'core_reset[1]'
            and manifest['AddedClockDomainCrossings'] == 0
            and manifest['StatusAvailable'] is False and manifest['UnderflowsAvailable'] is False,
            'statistics observation contract differs')
    require(manifest['IDsAreBitstreamHashes'] is False
            and manifest['InheritedRoutedTiming'] is False
            and manifest['HardwareReleaseAllowed'] is False
            and manifest['OpticalCorrectionAccepted'] is False,
            'source manifest exceeds isolated candidate scope')
    require(plan['UARTPin'] == dict(source.UART_ATTRIBUTES), 'exact C24 UART contract required')


def recipe(source_plan_path, source_plan_sha, work, maximum=1800):
    work = work_path(work)
    require(type(maximum) is int and 60 <= maximum <= 1800, 'native build bound must be 60..1800 seconds')
    require(source_plan_sha == SOURCE_SHA and sha(source.SELF) == SOURCE_PRODUCER_SHA,
            'explicit frozen statistics source plan and producer required')
    watched = {}
    source_plan_path = source.bind(watched, source_plan_path, source_plan_sha)
    require(source_plan_path.parent != work, 'build must be separate from reviewed source preparation')
    frozen = source.verify(source_plan_path)
    manifest = read(frozen['SourceManifest'])
    fixed_source_contract(frozen, manifest)
    for path, h in {**frozen['InputSHA256'], **frozen['OutputSHA256']}.items():
        source.bind(watched, path, h)
    # Recompute the same nonfeedback source delta with only local include paths
    # relocated to this build. No old ADF or timing repair enters this recipe.
    prepared, payloads = source.recipe(frozen['BaselinePlan']['Path'], frozen['BaselinePlan']['SHA256'], work)
    require(prepared['BuildIdentitySHA256'] == frozen['BuildIdentitySHA256']
            and prepared['ProfileID'] == frozen['ProfileID'], 'source identity changed during relocation')
    new_manifest = json.loads(payloads[work/'source/manifest.json'])
    require(new_manifest == manifest, 'source manifest changed during relocation')
    baseline = read(frozen['BaselinePlan']['Path'])
    pds = baseline['PDS']
    tool = source.bind(watched, pds['Executable'], pds['ExecutableSHA256'])
    require(tool.name.casefold() == 'pds_shell.exe'
            and pds['ExpectedVersion'] == '2023.2-SP3 build 154097', 'exact current native PDS tool required')
    require(baseline['ExpectedActualStages'] == STAGES, 'baseline native stage sequence differs')
    for path in (SELF, RUNNER, CLEANUP, Path(sys.executable).resolve()):
        source.bind(watched, path)
    payloads[work/'source-plan.json'] = encoded(prepared)
    command = [str(tool), '-file', (work/'timing.tcl').as_posix(), '-work_dir', work.as_posix(), '-project_name', TARGET]
    plan = {'Schema': SCHEMA, 'Target': TARGET, 'Scope': 'PrepareOnlyNoEDA',
            'WorkDirectory': str(work), 'ProjectRoot': str(PROJECT), 'SourcePreparation': ref(source_plan_path),
            'SourceManifest': str(work/'source/manifest.json'), 'SourcePlan': str(work/'source-plan.json'),
            'BuildIdentitySHA256': frozen['BuildIdentitySHA256'], 'BuildID': frozen['BuildID'],
            'ProfileSHA256': PROFILE_SHA, 'HeaderSHA256': HEADER_SHA,
            'InputSHA256': watched, 'PreparedSHA256': {str(p): source.digest(data) for p,data in payloads.items()},
            'ExplicitDesigns': prepared['ExplicitDesigns'], 'RoleCounts': prepared['RoleCounts'],
            'Tcl': prepared['Tcl'], 'PDS': pds, 'CommandToRunSeparately': command,
            'ExpectedActualStages': STAGES, 'MaximumSecondsForExternalExecutor': maximum,
            'ExternalDeadlineRequired': True, 'HardwareAccessed': False, 'EDAExecuted': False,
            'BitstreamRequested': False, 'TimingAccepted': False, 'HardwareReleaseAllowed': False,
            'OpticalCorrectionAccepted': False, 'InheritedRoutedTiming': False,
            'ExpectedLiteralPinCount': 129, 'VideoControlFeedbackAdded': False,
            'Limits': 'Independent stats build only. New pin count, counter fanout and placement require '
                      'new IO/timing/CDC validation. Native diagnostic messages are retained and cannot '
                      'be reclassified by this executor. No bitstream or programming stage is allowed.'}
    require(all(sha(p) == h for p,h in watched.items()), 'input drift during build preparation')
    return plan, payloads


def prepare(source_plan_path, source_plan_sha, work, maximum=1800):
    plan, payloads = recipe(source_plan_path, source_plan_sha, work, maximum)
    work = Path(plan['WorkDirectory'])
    require(not work.exists(), 'fresh statistics native build directory required')
    for path, data in payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    plan['PreparedUTC'] = datetime.now(timezone.utc).isoformat()
    with (work/'plan.json').open('xb') as stream:
        stream.write(encoded(plan))
    return work/'plan.json'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-plan', type=Path, required=True)
    p.add_argument('--source-plan-sha256', required=True)
    p.add_argument('--work-dir', type=Path, required=True)
    p.add_argument('--maximum-seconds', type=int, default=1800)
    a = p.parse_args()
    out = prepare(a.source_plan, a.source_plan_sha256, a.work_dir, a.maximum_seconds)
    print(json.dumps({'Prepared': True, 'Plan': ref(out), 'EDAExecuted': False, 'HardwareAccessed': False}))


if __name__ == '__main__':
    main()
