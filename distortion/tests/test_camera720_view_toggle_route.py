"""Exact hold-only recipes and independently checked native save receipts."""
import copy
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import camera720_view_toggle_route as physical
import camera720_view_toggle_receipts as receipts


@pytest.fixture
def request_case(tmp_path, monkeypatch):
    """Small synthetic receipts; native binding and parser tested elsewhere."""
    monkeypatch.setattr(physical.build, 'ROOT', tmp_path)
    serializer = tmp_path / 'serializer.py'
    serializer.write_text('# Synthetic serializer dependency; not executed by request binding.\n', encoding='ascii')
    monkeypatch.setattr(physical.preservation, 'SERIALIZER', serializer)
    build = tmp_path / 'build' / 'plan.json'
    build.parent.mkdir()
    build.write_text('{}', encoding='ascii')
    source = build.parent / 'place_route' / (physical.TARGET + '_pnr.adf')
    source.parent.mkdir()
    source.write_bytes(b'original candidate ADF')
    row1 = {'Source': 'source0/CLK', 'Endpoint': 'sink0/TX_DATA[5]',
            'ActualLaunchOutputs': ['source0/L5Q', 'source0/L6Q']}
    row2 = {'Source': 'source1/ICLKDIV', 'Endpoint': 'sink1/D',
            'ActualLaunchOutputs': ['source1/RX_DATA[7]']}
    actual = {'CreatedUTC': 'fresh', 'Paths': [row1, row2],
              'MissingExactSetup': [], 'MissingLaunchCases': [], 'HoldFailingPathCount': 2}
    values, request = {}, {'Schema': physical.REQUEST_SCHEMA, 'Target': physical.TARGET,
                          'BuildPlan': physical.ref(build)}
    for role, mode in [('ExportReceipt', 'export'), ('RouteReceipt', 'report'), ('QueryReceipt', 'query')]:
        work = tmp_path / mode
        work.mkdir()
        p = work / 'result.json'
        p.write_text('{}', encoding='ascii')
        value = {'Mode': mode, 'BuildPlan': str(build), 'SourceADF': str(source),
                 'SourceADFSHA256': physical.sha(source), 'Artifacts': {}}
        values[p] = value
        request[role] = physical.ref(p)
    full = tmp_path / 'export' / 'report_timing' / (physical.TARGET + '.rtr')
    full.parent.mkdir()
    full.write_text('synthetic native full report', encoding='ascii')
    values[tmp_path / 'export' / 'result.json']['Artifacts'][full.relative_to(full.parents[1]).as_posix()] = physical.sha(full)
    extras = []
    for i, (row, through) in enumerate([(row1, row1['ActualLaunchOutputs'][0]),
                                       (row1, row1['ActualLaunchOutputs'][1]),
                                       (row2, row2['ActualLaunchOutputs'][0])]):
        p = tmp_path / 'query' / 'report_path_timing' / str(i) / 'report_timing' / (physical.TARGET + '.rtr')
        p.parent.mkdir(parents=True)
        p.write_text('| Tcl Command : report_path_timing -from {t:' + row['Source'] +
                     '} -through {t:' + through + '} -to {t:' + row['Endpoint'] + '}\n', encoding='ascii')
        values[tmp_path / 'query' / 'result.json']['Artifacts'][p.relative_to(tmp_path / 'query').as_posix()] = physical.sha(p)
        extras.append(p)
    dump = tmp_path / 'report' / 'route-dump.txt'
    dump.write_text('synthetic native route dump', encoding='ascii')
    values[tmp_path / 'report' / 'result.json']['Artifacts']['route-dump.txt'] = physical.sha(dump)
    analysis = tmp_path / 'analysis.json'
    analysis.write_text(json.dumps({**actual, 'CreatedUTC': 'original'}), encoding='ascii')
    request['HoldAnalysis'] = physical.ref(analysis)
    wire = tmp_path / 'wire.txt'
    wire.write_text('wire fixture', encoding='ascii')
    route = {'Commands': ['route fixture'], 'WirePattern': physical.ref(wire)}
    route_path = tmp_path / 'route.json'
    route_path.write_text(json.dumps(route), encoding='ascii')
    request['RoutePlan'] = physical.ref(route_path)
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request), encoding='ascii')
    monkeypatch.setattr(physical.build, 'validate', lambda p: {'PDS': {'Executable': 'pds'}})
    monkeypatch.setattr(receipts, 'bind_native_receipt', lambda p: (values[p], {}))
    monkeypatch.setattr(physical.hold, 'extract', lambda full, extras: (copy.deepcopy(actual), {}, ''))
    monkeypatch.setattr(physical.hold, 'derive_waypoints', lambda analysis, dump: copy.deepcopy(route))
    return path, request, values, actual, route, extras


def save_request(case):
    case[0].write_text(json.dumps(case[1]), encoding='ascii')


def test_request_rederives_current_analysis_and_all_three_launch_reports(request_case):
    value, plan, source, route, watched = physical.bind_request(request_case[0])
    assert source.name == physical.TARGET + '_pnr.adf'
    assert route == request_case[4]
    assert str(Path(physical.__file__).resolve()) in watched
    serializer = physical.preservation.SERIALIZER
    assert watched[str(serializer)] == physical.sha(serializer)
    assert value == request_case[1]


def test_request_rejects_missing_serializer_dependency(request_case):
    physical.preservation.SERIALIZER.unlink()
    with pytest.raises(FileNotFoundError):
        physical.bind_request(request_case[0])


def test_request_rejects_serializer_changed_after_binding(request_case, monkeypatch):
    serializer = physical.preservation.SERIALIZER
    original_sha = physical.sha
    changed = False

    def hash_then_change(path):
        nonlocal changed
        digest = original_sha(path)
        if Path(path) == serializer and not changed:
            serializer.write_text('# Changed after dependency binding.\n', encoding='ascii')
            changed = True
        return digest

    monkeypatch.setattr(physical, 'sha', hash_then_change)
    with pytest.raises(ValueError, match='hold route input drift'):
        physical.bind_request(request_case[0])
    assert changed


@pytest.mark.parametrize('extra', ['Commands', 'ResetProof', 'SourceADF'])
def test_request_cannot_inject_reset_commands_or_alternate_source(request_case, extra):
    request_case[1][extra] = []
    save_request(request_case)
    with pytest.raises(ValueError, match='exact hold-route request'):
        physical.bind_request(request_case[0])


@pytest.mark.parametrize('change', ['missing_report', 'wrong_selector', 'analysis_drift', 'route_drift', 'wrong_mode', 'wrong_adf'])
def test_request_rejects_incomplete_or_substituted_evidence(request_case, change):
    path, request, values, actual, route, extras = request_case
    if change == 'missing_report':
        extras[0].unlink()
    elif change == 'wrong_selector':
        p = extras[0]
        p.write_text(p.read_text().replace('source0/L5Q', 'unrelated/L5Q'), encoding='ascii')
        values[Path(request['QueryReceipt']['Path'])]['Artifacts'][p.relative_to(Path(request['QueryReceipt']['Path']).parent).as_posix()] = physical.sha(p)
    elif change == 'analysis_drift':
        actual['HoldFailingPathCount'] = 1
    elif change == 'route_drift':
        route['Commands'] = ['injected alternate route']
    elif change == 'wrong_mode':
        values[Path(request['RouteReceipt']['Path'])]['Mode'] = 'export'
    else:
        values[Path(request['QueryReceipt']['Path'])]['SourceADFSHA256'] = '0' * 64
    with pytest.raises(ValueError):
        physical.bind_request(path)


def test_render_initializes_before_route_and_saves_only_working_copy(tmp_path):
    work = tmp_path / 'space in work'
    commands = ['unroute fixture', 'route fixture']
    text = physical.render(commands, work)
    assert text.count(physical.INIT) == 1
    assert text.index(physical.INIT) < text.index('post-init.adf') < text.index(commands[0])
    assert text.index(commands[1]) < text.index('save_adif') < text.index('saved-route.adf')
    assert '{' + work.as_posix() + '/input.adf}' in text
    assert text.count(physical.MARKER) == 1
    assert not any(s in text for s in ('set_false_path', 'set_clock_groups', 'gen_bit_stream', 'program_device'))


@pytest.fixture
def completed_case(tmp_path, monkeypatch):
    for name, payload in [('stage-plan.json', b'{}'), ('input.adf', b'routed ADF'),
                          ('saved-route.adf', b'routed ADF'), ('post-init.adf', b'original ADF'),
                          ('route-dump.txt', b'new route'), ('old-route.txt', b'old route'),
                          ('stdout.log', (physical.MARKER + '\n').encode()), ('stderr.log', b'')]:
        (tmp_path / name).write_bytes(payload)
    comparison = {'Passed': True}
    plan = {'InputSHA256': {}, 'SourceADFSHA256': physical.sha(tmp_path / 'post-init.adf'),
            'OriginalRouteDump': physical.ref(tmp_path / 'old-route.txt'), 'MeasuredTargets': [], 'Routes': []}
    value = {**plan, 'ExecutionPassed': True, 'EDAExecuted': True, 'ExitCode': 0, 'TimedOut': False,
             'InputDrift': [], 'Diagnostics': [], 'ActualEvents': [], 'CompletionMarker': True,
             'Cleanup': {'Complete': True}, 'InitializationPreservedADF': True, 'SavedADFReadbackMatches': True,
             'StagePlanSHA256': physical.sha(tmp_path / 'stage-plan.json'),
             'ResultADF': physical.ref(tmp_path / 'input.adf'), 'ResultADFSHA256': physical.sha(tmp_path / 'input.adf'),
             'RouteComparison': comparison, 'Artifacts': {p.name: physical.sha(p) for p in tmp_path.iterdir()}}
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(value), encoding='ascii')
    monkeypatch.setattr(physical, 'bind_plan', lambda p: plan)
    monkeypatch.setattr(physical.preservation, 'compare_route_dumps', lambda *args: comparison)
    return path, value


def test_completed_receipt_reconstructs_route_preservation(completed_case):
    path, value = completed_case
    result, watched = physical.bind_completed(path)
    assert result == value and str(path) in watched


@pytest.mark.parametrize('field,changed', [('ExitCode', 1), ('TimedOut', True), ('EDAExecuted', False),
    ('InputDrift', ['changed']), ('Diagnostics', ['E: native failure']),
    ('ActualEvents', [['Route', 'started']]), ('CompletionMarker', False),
    ('Cleanup', {'Complete': False}), ('InitializationPreservedADF', False), ('SavedADFReadbackMatches', False)])
def test_completed_receipt_cannot_trust_success_flag_over_failed_execution(completed_case, field, changed):
    path, value = completed_case
    value[field] = changed
    path.write_text(json.dumps(value), encoding='ascii')
    with pytest.raises(ValueError):
        physical.bind_completed(path)


def test_completed_receipt_cannot_hide_native_error_log(completed_case):
    path, value = completed_case
    log = path.parent / 'stdout.log'
    log.write_text(physical.MARKER + '\nE: native route error\n', encoding='ascii')
    value['Artifacts']['stdout.log'] = physical.sha(log)
    path.write_text(json.dumps(value), encoding='ascii')
    with pytest.raises(ValueError):
        physical.bind_completed(path)


@pytest.mark.parametrize('text', ['native process stopped without save marker\n',
                                  'Process "Route" started.\n' + physical.MARKER + '\n'])
def test_actual_native_log_must_prove_completion_without_new_stage(completed_case, text):
    path, value = completed_case
    log = path.parent / 'stdout.log'
    log.write_text(text, encoding='ascii')
    value['Artifacts']['stdout.log'] = physical.sha(log)
    path.write_text(json.dumps(value), encoding='ascii')
    with pytest.raises(ValueError):
        physical.bind_completed(path)


def test_completed_artifact_inventory_cannot_omit_files(completed_case):
    path, value = completed_case
    value['Artifacts'].pop('route-dump.txt')
    path.write_text(json.dumps(value), encoding='ascii')
    with pytest.raises(ValueError):
        physical.bind_completed(path)


def test_saved_copy_and_result_adf_must_have_same_digest(completed_case):
    path, value = completed_case
    saved = path.parent / 'saved-route.adf'
    saved.write_bytes(b'another candidate ADF')
    value['Artifacts']['saved-route.adf'] = physical.sha(saved)
    value['ResultADFSHA256'] = physical.sha(saved)
    path.write_text(json.dumps(value), encoding='ascii')
    with pytest.raises(ValueError):
        physical.bind_completed(path)
