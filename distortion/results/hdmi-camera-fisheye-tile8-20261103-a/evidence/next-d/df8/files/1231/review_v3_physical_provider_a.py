"""Independent source/pure-behavior review. No provider derivation or EDA."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from types import SimpleNamespace
import argparse
import ast
import hashlib
import importlib.util
import json
import re
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'distortion'
TOOLS = ROOT / 'tools'
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
KINDS = ('physical', 'scoped_native', 'target_query', 'physical_checks', 'final', 'bitstream', 'program')
NEW = [TOOLS / ('hdmi_camera_fisheye_tile8df8v3_' + kind + '.py') for kind in KINDS]
OBSERVER = TOOLS / 'hdmi_camera_fisheye_tile8df8v3_application_observer.py'


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def namespace(text):
    return text.replace('tile8df8v2', 'tile8df8v3').replace('TILE8DF8V2', 'TILE8DF8V3')


def function(tree, name):
    return next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name)


def isolated_function(node, globals_):
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<peer-pure-function>', 'exec'), globals_)
    return globals_[node.name]


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--output', type=Path, required=True); a = ap.parse_args()
    output = a.output.resolve(); require(output.parent == HERE and not output.exists(), 'fresh isolated peer report required')
    sources = NEW + [OBSERVER] + [TOOLS / ('hdmi_camera_fisheye_tile8df8v2_' + kind + '.py') for kind in KINDS]
    sources += [WORK / 'physical-release-provider-source-manifest-a.json', WORK / 'root-independent-complete-source-review-a.json', Path(__file__).resolve()]
    before = {str(p): sha(p) for p in sources}
    require(before[str(WORK / 'physical-release-provider-source-manifest-a.json')] == '8914c4c46ab950866747400cf1d668f3436720e562f10d76870c4440019fb50d', 'original 991-source manifest differs')
    require(before[str(WORK / 'root-independent-complete-source-review-a.json')] == '27e614d3e584d1a8a278254b12fba992462a19a76bda445d54528a70012a9374', 'original root review differs')
    for kind in KINDS[1:]:
        old = ast.parse(namespace((TOOLS / ('hdmi_camera_fisheye_tile8df8v2_' + kind + '.py')).read_text()))
        new = ast.parse((TOOLS / ('hdmi_camera_fisheye_tile8df8v3_' + kind + '.py')).read_text())
        require(ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False), 'non-namespace change in ' + kind)
    oldtree = ast.parse(namespace((TOOLS / 'hdmi_camera_fisheye_tile8df8v2_physical.py').read_text()))
    newtree = ast.parse(NEW[0].read_text())
    oldf = {x.name: x for x in oldtree.body if isinstance(x, ast.FunctionDef)}
    newf = {x.name: x for x in newtree.body if isinstance(x, ast.FunctionDef)}
    require(set(oldf) == set(newf), 'physical public function set differs')
    changed = sorted(k for k in oldf if ast.dump(oldf[k], include_attributes=False) != ast.dump(newf[k], include_attributes=False))
    require(changed == sorted(('application_recipe', 'render_application', 'application_evidence', 'execute_application')), 'unexpected physical semantic delta')
    require(ast.dump(oldf['_bind_application'], include_attributes=False) == ast.dump(newf['_bind_application'], include_attributes=False), 'application bind gates changed')
    require(ast.dump(oldf['check_application'], include_attributes=False) == ast.dump(newf['check_application'], include_attributes=False), 'public full recipe recheck changed')

    spec = importlib.util.spec_from_file_location('v3_observer_peer_only', OBSERVER)
    obs = importlib.util.module_from_spec(spec); spec.loader.exec_module(obs)
    value = json.loads((WORK / 'physical-v2-a/stage-plan.json').read_text())
    fixture = {k: value[k] for k in ('RepoAlias', 'WorkDirectory', 'QueryBody', 'ExactCommands')}; del value
    fixture['WorkDirectory'] = str(WORK / 'physical-v3-a')
    common = {'Path': Path, 'build': SimpleNamespace(ROOT=ROOT, paths=SimpleNamespace(alias_path=lambda *args: '@WORK@')),
              'native': SimpleNamespace(INIT='mpnr_report_timing -force_to_run -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE'),
              'MARKER': 'PEER_NAMESPACE_NORMALIZED_FINAL_MARKER'}
    old_render = isolated_function(oldf['render_application'], dict(common))(fixture)
    new_render = isolated_function(newf['render_application'], {**common, 'observation': obs})(fixture)
    require(obs.strip_markers(new_render) == old_render, 'observer-stripped complete Tcl differs from original application')
    patterns = lambda text: Counter(re.findall(r'get_pins -hierarchical -regexp \{([^{}]+)\}', text))
    require(patterns(old_render) == patterns(new_render) and len(patterns(new_render)) == 650 and sum(patterns(new_render).values()) == 3343,
            'native selector inventory/multiplicity changed')
    require(len(fixture['ExactCommands']) == 1096 and len(fixture['QueryBody'].splitlines()) == 55, 'actual frozen command fixture differs')
    for bad in ('[clock', '[format', '[string', '[open', 'catch {'):
        require(bad not in new_render, 'formal application introduced unsupported compatibility wrapper: ' + bad)
    strip_negatives = 0
    for bad in ('puts {' + obs.PREFIX + '|BAD LABEL}\nflush stdout\n',
                'puts {' + obs.PREFIX + '|INIT|BEGIN}\n',
                'puts {' + obs.PREFIX + '|INIT|BEGIN}\nflush stderr\n'):
        try: obs.strip_markers(bad)
        except ValueError: strip_negatives += 1
        else: raise ValueError('malformed marker stripping accepted')

    # Stop at the first audit call: no real audit/provider/final/bit is derived.
    def audit_boundary(*args): raise RuntimeError('pure-audit-boundary')
    budget = isolated_function(newf['application_recipe'], {'build': SimpleNamespace(work_path=lambda p: p), 'require': require,
                               'bind_audit': audit_boundary})
    rejected = []
    for maximum in (0, 59, 1801, True, 1800.0):
        try: budget(None, None, None, Path('.'), maximum)
        except ValueError: rejected.append(str(maximum))
        else: raise ValueError('invalid application budget accepted')
    for maximum in (600, 1800):
        try: budget(None, None, None, Path('.'), maximum)
        except RuntimeError as error: require(str(error) == 'pure-audit-boundary', 'unexpected budget control error')
        else: raise ValueError('budget positive control did not reach audit boundary')

    with tempfile.TemporaryDirectory(prefix='v3-observer-peer-', dir=HERE) as name:
        temp = Path(name).resolve(); require(temp.is_relative_to(HERE), 'owned temporary fixture escaped output directory')
        stdout = temp / 'stdout.log'; stdout.write_bytes(b'ordinary\n' + (obs.PREFIX + '|QUERY|0|BE').encode())
        host = obs.HostObserver(temp, time.monotonic()); host.poll(); require(not host.records, 'partial marker counted before newline')
        with stdout.open('ab') as stream:
            stream.write(b'GIN\nI: Timing-5001: synthetic-only\n' + (obs.PREFIX + '|QUERY|0|RETURN\n').encode())
        host.poll(); host.poll(); summary = host.close()
        require(len(summary['Markers']) == 2 and summary['ObservedNativeTiming5001Lines'] == 1, 'observer duplicate/lost append')
        require(summary['Markers'][0]['ObservedHostMonotonicNS'] <= summary['Markers'][1]['ObservedHostMonotonicNS'], 'host observation clock reversed')
        require(all(x['ExternalHostObservationNotNativeInternalTime'] is True for x in summary['Markers']) and
                summary['ConfiguredPollingDoesNotBoundNativeStdioBufferingOrOSSchedulingDelay'] is True and
                summary['ObservationCreatesNoSelectorOrPhysicalAcceptance'] is True, 'observation claims native authority')
        require(all(datetime.fromisoformat(x['ObservedUTC']).tzinfo is not None for x in summary['Markers']), 'host UTC missing timezone')
        faildir = temp / 'close-error'; faildir.mkdir(); failed = obs.HostObserver(faildir, time.monotonic()); failed.path = faildir
        try: failed.close()
        except OSError: pass
        else: raise ValueError('observer read error did not propagate')
        require(failed.output.closed, 'observer output remains open after close/read error')
    code = NEW[0].read_text()
    require("remaining=value['MaximumSeconds']-(time.monotonic()-start)" in code and 'process.wait(timeout=min(observation.POLL_SECONDS,remaining))' in code,
            'execution is not bounded by actual declared application maximum')
    require('build.cleanup.stop_owned_tree(process,work' in code and 'observer.close()' in code and
            "except Exception as error:result['Error']=" in code and "and not result.get('Error')" in code,
            'cleanup/observer error no longer prevents execution acceptance')
    after = {str(p): sha(p) for p in sources}; require(before == after, 'source changed during independent review')
    result = {'Schema': 'tile8df8v3-physical-provider-independent-source-review-v1', 'Passed': True,
              'IndependentPeerReviewPerformed': True, 'ProviderRevision': 'tile8df8v3-budget1800-a',
              'CheckedUTC': datetime.now(timezone.utc).isoformat(), 'BlockingFindings': [], 'InputDrift': [],
              'ReviewScope': 'Eight new provider files; namespace equivalence, application budget, complete Tcl stripping and pure observer/error behavior. Driver/freeze/roles/prewarm are reviewed separately.',
              'NamespaceOnlyModules': list(KINDS[1:]), 'PhysicalChangedFunctions': changed,
              'PublicCheckApplicationAndBindGatesUnchangedExceptNamespace': True,
              'CompleteObserverStrippedTclExactlyMatchesV2AfterPathAndMarkerNormalization': True,
              'ActualNativeSelectorPatterns': 650, 'ActualNativeSelectorOccurrences': 3343,
              'ActualExactCommands': 1096, 'ActualQueryBodyCommands': 55,
              'MalformedMarkerStripCasesRefused': strip_negatives, 'InvalidBudgetCasesRefused': rejected,
              'Budget600And1800ReachAuditBoundaryOnly': True,
              'SyntheticObserver': {'IncrementalAndPartialLines': True, 'NoDuplicateMarkers': True,
                  'TrueHostUTCAndMonotonicNS': True, 'VendorBufferingAndSchedulingUncertaintyDisclosed': True,
                  'ReadErrorPropagatesAndClosesOutput': True, 'NotNativeTimingOrSelectorEvidence': True},
              'ObserverFailurePreventsExecutionAcceptanceAfterOwnedCleanup': True,
              'ActualPhysicalExecutionOrFinalProofVerified': False, 'ProviderImportedOrExecuted': False,
              'OnlyObserverModuleAndIsolatedASTFunctionsUsedForPureTests': True,
              'EDAExecuted': False, 'HardwareAccessed': False, 'PDriveAccessed': False,
              'PhysicalAcceptanceInherited': False, 'TimingAccepted': False, 'HardwareReleaseAllowed': False,
              'InputSHA256': before}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'Passed': True, 'Path': str(output), 'SHA256': sha(output), 'ProviderFiles': 8, 'BlockingFindings': []}))


if __name__ == '__main__': main()
