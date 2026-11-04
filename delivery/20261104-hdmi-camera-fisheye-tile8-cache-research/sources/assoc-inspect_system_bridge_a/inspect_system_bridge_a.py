"""CPU-only proof of the frozen system input bridge, before new-cache gates exist."""
from pathlib import Path
import importlib.util
import json

HERE = Path(__file__).resolve().parent


def main():
    source = HERE / 'run_assoc_system_a.py'
    spec = importlib.util.spec_from_file_location('assoc_system_bridge_inspection', source)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    evidence = runner.Evidence()
    evidence.add(Path(__file__))
    evidence.add(source)
    checked = {}
    canonical = {}
    for kind in ('normal', 'sustained'):
        for mode in ('small', 'native'):
            work, receipt, saved = runner.baseline(kind, mode, evidence)
            actual_sources = {}
            for name, row in saved['CompileSnapshot'].items():
                evidence.add(row['Path'], row['SHA256'])
                data = Path(row['Path']).read_bytes()
                if name == runner.CACHE:
                    continue  # The new cache is deliberately not pinned yet.
                if name == runner.ENGINE:
                    changed = runner.change_engine(data)
                    assert changed.replace(b'.INDEX_BITS(10)', b'.INDEX_BITS(8)') == data
                    data = changed
                actual_sources[name] = runner.digest(data)
            assert len(actual_sources) == 21
            assert len(saved['FixtureSHA256']) == 17
            for name, pin in saved['FixtureSHA256'].items():
                evidence.add(work / name, pin)
            old_config = (work / 'config.vh').read_bytes()
            new_config = runner.change_config(old_config)
            assert new_config.replace(b'SIM_CACHE_INDEX_BITS=10', b'SIM_CACHE_INDEX_BITS=8') == old_config
            for path in (work / 'relocated-headers').rglob('*.vh'):
                name = path.relative_to(work / 'relocated-headers').as_posix()
                evidence.add(path, saved['SourceSHA256'][name])
                actual_sources['headers/' + name] = runner.sha(path)
            assert len(actual_sources) == 24
            key = kind + '-' + mode
            canonical[key] = actual_sources
            checked[key] = {
                'BaselineReceipt': runner.ref(receipt),
                'OriginalPreparedSourceCount': len(saved['CompileSnapshot']),
                'TwentyPreparedSourcesAndBenchWillBeUnchanged': True,
                'EngineIndex8To10OnlySHA256': actual_sources[runner.ENGINE],
                'ExpectedConfigIndex8To10OnlySHA256': runner.digest(new_config),
                'OriginalFixtureCount': 17, 'OracleAndTimingFixturesRetainedExactly': 16,
                'HeaderCount': 3, 'PreparedHashesExcludingUnreadyCache': actual_sources,
                'IndependentOracleGeometry': {
                    name: saved['Fixture'][name] for name in ('Width', 'Height', 'HT', 'VT')},
            }
        assert canonical[kind + '-small'] == canonical[kind + '-native']
    rejects = 0
    for transform, data in ((runner.change_engine, b'.INDEX_BITS(9)'),
                            (runner.change_engine, b'.INDEX_BITS(8).INDEX_BITS(8)'),
                            (runner.change_config, b'SIM_CACHE_INDEX_BITS=9'),
                            (runner.change_config, b'SIM_CACHE_INDEX_BITS=8 SIM_CACHE_INDEX_BITS=8')):
        try:
            transform(data)
        except ValueError:
            rejects += 1
        else:
            raise AssertionError('nonunique or wrong original parameter accepted')
    assert rejects == 4
    drift = evidence.drift()
    assert not drift
    report = {
        'Schema': 'tile8-assoc2way256-system-bridge-preparation-v1', 'Passed': True,
        'ObservedUTC': runner.utc(), 'BridgeCases': checked,
        'SmallNativeCanonicalOtherSourcesMatchForBothKinds': True,
        'FiniteTransformRejectCases': rejects,
        'ActualNewCacheOrGateSHA256Pinned': False,
        'UnitAndIndependentBoundaryGateVerificationStillRequired': True,
        'SimulationAllowedByThisPreparationReport': False,
        'SourceContractCreated': False, 'XSimExecuted': False,
        'NativeEDAExecuted': False, 'HardwareAccessed': False,
        'TimingOrBoardAcceptance': False,
        'InputSHA256': evidence.inputs, 'InputDrift': drift,
    }
    target = HERE / 'system-bridge-preparation-a.json'
    runner.write(target, report)
    print(json.dumps({'Passed': True, 'Output': runner.ref(target),
                      'Inputs': len(evidence.inputs), 'SimulationsStarted': 0}))


if __name__ == '__main__':
    main()
