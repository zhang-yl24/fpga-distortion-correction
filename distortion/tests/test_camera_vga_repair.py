from pathlib import Path
import json
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_camera_vga_repair as repair
import run_camera_vga_derived as derived


def test_exact_single_net_and_multiple_waypoints():
    rows = [{'Net': '_N101', 'Branch': 'M3:CLMS_345_769',
             'Pins': 'ZDNE[1]:SRB_342_768>IDNE[1]:SRB_348_774;ZDNE[2]:SRB_348_774>IDNE[2]:SRB_354_780;'}]
    commands = repair.route_commands(rows)
    assert len(commands) == 4
    assert commands[1] == 'unroute -branch {_N101:M3:CLMS_345_769;}'
    assert 'manual_route -net {_N101}' in commands[2]


@pytest.mark.parametrize('row', [
    {'Net': '_N107', 'Branch': 'M3:CLMS_345_769', 'Pins': 'A:SRB_1_2>B:SRB_3_4;'},
    {'Net': '_N101', 'Branch': 'M3:CLMS_345_769; exec calc', 'Pins': 'A:SRB_1_2>B:SRB_3_4;'},
    {'Net': '_N188', 'Branch': 'D:CLMA_351_774', 'Pins': '[exec calc]'},
    {'Net': '_N78', 'Branch': 'D:CLMA_351_774', 'Pins': 'A:SRB_1_2>B:SRB_3_4;', 'Extra': 'unsafe'},
])
def test_route_injection_and_unrelated_nets_rejected(row):
    with pytest.raises(ValueError):
        repair.route_commands([row])


def test_repeated_net_rejected():
    row = {'Net': '_N101', 'Branch': 'M3:CLMS_345_769', 'Pins': 'A:SRB_1_2>B:SRB_3_4;'}
    with pytest.raises(ValueError):
        repair.route_commands([row, row])


def test_render_has_no_synthesis_and_saves_independent_copy():
    text = repair.render(['show -design_net {_N101}'], repair.core.ROOT / 'repair-cpu-test')
    assert 'save_adif' in text and '/pre-sta.adf' in text
    assert 'mpnr_report_timing' in text and 'manual_route' not in text
    assert 'synthesize ' not in text and '\npnr ' not in text
    assert '-max_path 20 ' not in text
    assert text.count('mpnr_report_timing ')==1


@pytest.mark.parametrize('route_commands', [[], ['show -design_net {_N101}']])
def test_reset_render_initializes_native_timing_before_get_pins(route_commands):
    reset='set_false_path -from [get_pins -hierarchical -regexp {^(reset/CLK)$}] -to [get_pins -hierarchical -regexp {^(native/RS)$}]'
    text=repair.render(route_commands+[reset],repair.core.ROOT/'reset-cpu-test')
    initialization='mpnr_report_timing -force_to_run -delay_type min_max -max_path 20 -nworst 4 -report_exception TRUE'
    final='mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE'
    assert text.index('mpnr -input ') < text.index(initialization) < text.index(reset)
    assert text.index(reset) < text.index('save_adif') < text.index(final)
    assert text.count(initialization)==1 and text.count(final)==1


def test_derived_wrapper_accepts_unchanged_original_baseline():
    plan, watched = derived.bind_derived(repair.core.ORIGINAL)
    assert plan['Target'] == repair.core.TARGET
    assert watched[repair.core.ORIGINAL] == repair.core.BASE_SHA
    assert repair.core.check_inputs(watched) == []


def test_reset_requires_complete_native_connectivity_proof(tmp_path, monkeypatch):
    source, target = 'reset/CLK', 'native[0]/RS'
    patterns = ['^(' + re.escape(n) + ')$' for n in (source, target)]
    command = 'set_false_path -from [get_pins -hierarchical -regexp {' + patterns[0] + '}] -to [get_pins -hierarchical -regexp {' + patterns[1] + '}]'
    fdc = tmp_path / 'scope.fdc'
    fdc.write_text(command + '\n')
    scope_plan = tmp_path / 'plan.json'
    scope_plan.write_text('{}')
    proofpath = tmp_path / 'proof.json'
    binding = lambda p: {'Path': str(p), 'SHA256': repair.core.sha(p)}
    proof = {'Schema': 'camera-vga-reset-proof-v1', 'SourceADFSHA256': repair.core.BASE_SHA,
             'NativeQueriesVerified': True, 'EntryConnectivityVerified': True,
             'InternalConnectivityVerified': True, 'TimingExceptionApproved': True,
             'ProposedFDC': binding(fdc), 'ScopePlan': binding(scope_plan),
             'InputSHA256': {str(scope_plan): repair.core.sha(scope_plan)},
             'NativeQueries': [{'Source': source, 'Targets': [target], 'ExpectedFromCount': 1,
                                'ExpectedTargetCount': 1, 'FromRegex': patterns[0], 'ToRegex': patterns[1]}]}
    proofpath.write_text(json.dumps(proof))
    monkeypatch.setattr(repair.core, 'ROOT', tmp_path)
    monkeypatch.setattr(repair.core, 'PROJECT', tmp_path / 'distortion')
    scope = {'FDC': binding(fdc), 'Proof': binding(proofpath)}
    assert repair.reset_commands(scope, repair.core.BASE_SHA, {}) == [command]
    proof['InternalConnectivityVerified'] = False
    proofpath.write_text(json.dumps(proof))
    scope['Proof'] = binding(proofpath)
    with pytest.raises(ValueError, match='incomplete'):
        repair.reset_commands(scope, repair.core.BASE_SHA, {})
