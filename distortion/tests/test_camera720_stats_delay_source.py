"""Source isolation and the exact telemetry delta; no EDA or hardware."""
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))
import prepare_camera720_stats_delay_source as prep

BASE = ROOT / 'work/camera720-calibrated/build-a/plan.json'
BASE_SHA = '6774df13e1b0d3b2ad4d91764b59383c235437c12ede58c4c9bef5e007f36548'


def minimal_top():
    return ('module camera720_calibrated_top #(parameter A=1)(\n'
            '    input clk_27m,clk_p,clk_n,reset_n,\n'
            '''    output x
);
    raw_camera_input_delay camera_data_delay(.pad_data(cam_data),.capture_data(delayed_cam_data));
    thing system(.cam_vsync(cam_vsync),.cam_href(cam_href),.cam_data(delayed_cam_data));
    thing monitor(.ref_clk(clk_27m),.pclk(cam_pclk),.rst_n(global_reset_n),
        .vsync_active(!cam_vsync),.href_active(!cam_href));
assign x=reset_n;
endmodule
''')


def pin_reference():
    return '\n'.join(f'define_attribute {{p:uart_txd}} {{{k}}} {{{v}}}'
                     for k, v in prep.UART_ATTRIBUTES)


def test_top_delta_can_be_removed_byte_for_byte():
    old = minimal_top()
    new = prep.render_top(old, '123456789abcdef0', 'fedcba9876543210')
    block = re.search(r'\n    // Read-only observations.*?\.tx\(uart_txd\)\);\n', new, re.S).group()
    restored = new.replace(block, '', 1).replace('    output uart_txd,\n', '', 1).replace(prep.TARGET, prep.BASE_TARGET, 1)
    controls = re.search(r'    wire delayed_cam_href, delayed_cam_vsync;.*?capture_vsync\(delayed_cam_vsync\)\);\n', restored, re.S).group()
    restored = restored.replace(controls, '', 1).replace('.cam_vsync(delayed_cam_vsync),.cam_href(delayed_cam_href)', '.cam_vsync(cam_vsync),.cam_href(cam_href)', 1)
    assert restored == old
    assert '.vsync_active(!cam_vsync),.href_active(!cam_href)' in new
    assert '.ref_clk(clk_27m),.pclk(cam_pclk),.rst_n(global_reset_n)' in new
    assert '.clk(core_clk),.rst_n(core_reset[1])' in block
    assert '.source_accepted(captured_frames),.processed(processed_frames)' in block
    assert '.unique_presented(presented_frames)' in block
    assert ".status_valid(1'b0),.failed(1'b0),.fault(8'b0)" in block
    assert 'underflows' not in block.split('camera720_core_stats_uart', 1)[1]
    assert not re.search(r'\b(?:assign|always|reg|wire)\b', block)


@pytest.mark.parametrize('change', [
    lambda s: s.replace('input clk_27m,', 'input another_clk,'),
    lambda s: s + s,
    lambda s: s.replace('output x', 'output uart_txd'),
    lambda s: s.replace('endmodule', '// camera720_core_stats_uart\nendmodule'),
])
def test_changed_top_contract_is_rejected(change):
    with pytest.raises(ValueError):
        prep.render_top(change(minimal_top()), '1'*16, '2'*16)


def test_constraint_delta_preserves_all_original_bytes_and_adds_only_five_uart_attributes():
    old = 'create_clock -name core -period 8 [get_ports clk]\n'
    new = prep.render_fdc(old, pin_reference())
    assert new.startswith(old)
    assert new.count('p:uart_txd') == 5
    assert 'set_false_path' not in new and 'set_max_delay' not in new


@pytest.mark.parametrize('old,reference', [
    ('define_attribute {p:another_pin} {PAP_IO_LOC} {C24}', pin_reference()),
    ('# uart_txd already declared', pin_reference()),
    ('', pin_reference().replace('{3.3}', '{1.8}')),
    ('', pin_reference() + '\n' + pin_reference()),
])
def test_occupied_pin_or_unproven_electrical_contract_rejected(old, reference):
    with pytest.raises(ValueError):
        prep.render_fdc(old, reference)


@pytest.mark.parametrize('label', ['0'*15, 'G'*16, '1'*17])
def test_identity_requires_exact_64bit_labels(label):
    with pytest.raises(ValueError):
        prep.render_top(minimal_top(), label, '2'*16)


@pytest.mark.parametrize('name', ['../old.v', '/tmp/top.v', 'x\\top.v'])
def test_source_names_cannot_escape_closure(name):
    with pytest.raises(ValueError):
        prep.relative_name(name)


def test_explicit_baseline_hash_is_required(tmp_path):
    with pytest.raises(ValueError, match='explicit complete'):
        prep.source_inputs(tmp_path/'missing', None, {})


@pytest.mark.skipif(not BASE.is_file(), reason='local frozen calibrated source fixture unavailable')
def test_actual_frozen_source_packaging_isolated_and_detects_generated_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, 'WORK', tmp_path)
    before = prep.sha(BASE)
    work = tmp_path/'candidate'
    out = prep.prepare(BASE, BASE_SHA, work)
    value = prep.verify(out)
    manifest = prep.read(value['SourceManifest'])
    assert manifest['RoleCounts']['ManifestSources'] == 114
    assert manifest['RoleCounts']['ExplicitVerilog'] == 33
    assert manifest['AddedSources'] == [prep.STATS, prep.UART, prep.CONTROL_DELAY]
    assert manifest['IDsAreBitstreamHashes'] is False
    assert value['NativeExecutorImplemented'] is False
    old = prep.read(BASE)
    old_manifest = prep.read(old['SourceManifest'])
    for name, h in old_manifest['SourceSHA256'].items():
        if name not in (prep.BASE_TOP, old_manifest['Constraint']):
            assert prep.sha(work/'source'/name) == h
    assert manifest['ProfileSHA256'] == old['CalibrationEvidence']['Profile']['SHA256']
    assert prep.sha(BASE) == before
    top = work/'compiled'/prep.TOP
    top.write_bytes(top.read_bytes().replace(b'.processed(processed_frames)', b'.processed(captured_frames)'))
    with pytest.raises(ValueError, match='generated statistics artifact changed'):
        prep.verify(out)
    with pytest.raises(ValueError, match='fresh statistics'):
        prep.prepare(BASE, BASE_SHA, work)
