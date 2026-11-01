"""CPU-only checks for calibrated query/export native boundaries."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_camera_vga_calibrated_inspect as inspect


BASE=inspect.prep.WORK/'cpu-build-never-executed'
WORK=inspect.prep.WORK/'test-inspection-never-executed'


def test_query_initializes_before_exact_native_objects():
    body='get_pins -hierarchical -regexp {^camera_configuration/status_reg[0]/Q$}\nshow -design_net {_EXAMPLE_NEW_NET}\n'
    tcl=inspect.render('query','',BASE,WORK,body)
    assert tcl.count(inspect.INIT)==1
    assert tcl.index('mpnr -input') < tcl.index(inspect.INIT) < tcl.index('get_pins')
    assert 'compile ' not in tcl and 'gen_netlist ' not in tcl
    assert tcl.index(inspect.MARKER)>tcl.index('show -design_net')


@pytest.mark.parametrize('body',[
    'set_false_path -from {a} -to {b}',
    'manual_route -net {_N188} -pins {a>b;}',
    'show -design_net {a}; exec {other}',
    'puts {x\\}\nexec {other}',
    'puts {x\\\n}; exec {other}',
    'mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE',
    'file copy {@WORK@/input.adf} {@WORK@/other.adf}',
    'puts {'+inspect.MARKER+'}',
    'gen_netlist -func_sim_only',
])
def test_query_rejects_mutation_substitution_and_second_init(body):
    with pytest.raises(ValueError):inspect.query_commands(body)


def test_query_route_dump_is_scoped_to_input_clone():
    body='.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/routes.txt}'
    tcl=inspect.render('query','',BASE,WORK,body)
    assert '@WORK@' not in tcl and str(WORK/'routes.txt').replace('\\','/') in tcl
    with pytest.raises(ValueError):
        inspect.query_commands(body.replace('/routes.txt','/../routes.txt'))


def test_exact_pin_regexp_preserves_safe_literal_bracket_escapes():
    body=r'get_pins -hierarchical -regexp {^camera_configuration/status_reg\[0\]/Q$}'
    assert inspect.query_commands(body)==[body]


def test_export_preserves_real_calibrated_build_context_and_selects_two_stages():
    plan, _, payload=inspect.prep.recipe(BASE)
    original=payload.decode('ascii')
    tcl=inspect.render('export',original,BASE,WORK)
    for design in plan['ExplicitDesigns']:
        assert 'add_design {'+design+'}' in tcl
    assert 'compile -top_module camera_vga_calibrated_top\n' in tcl
    assert tcl.count('report_timing -force_to_run')==1
    assert 'report_timing -force_to_run -input_db_file {'+WORK.as_posix()+'/input.adf}' in tcl
    assert 'gen_netlist -force_to_run -input_db_file {'+WORK.as_posix()+'/input.adf} -func_sim_only' in tcl
    assert 'file copy' not in tcl
    for command in ('manual_route','set_false_path','generate_bitstream','cfg_program'):
        assert command not in tcl


def test_export_rejects_different_build_suffix():
    original=inspect.prep.make_tcl([BASE/'compiled/design.v'], BASE/'compiled/pins.fdc', BASE/'compiled/route.rcf', BASE)
    with pytest.raises(ValueError,match='suffix'):
        inspect.render('export',original.replace('-max_path 1000','-max_path 20'),BASE,WORK)
    with pytest.raises(ValueError,match='no query body'):
        inspect.render('export',original,BASE,WORK,'puts {x}')


def test_snapshot_tool_and_source_drift_detected(tmp_path):
    f=tmp_path/'source.v';f.write_bytes(b'original')
    watched={f:inspect.sha(f)}
    assert inspect.drift(watched)==[]
    f.write_bytes(b'changed')
    assert inspect.drift(watched)==[str(f)]
    f.unlink()
    assert inspect.drift(watched)==[str(f)]
