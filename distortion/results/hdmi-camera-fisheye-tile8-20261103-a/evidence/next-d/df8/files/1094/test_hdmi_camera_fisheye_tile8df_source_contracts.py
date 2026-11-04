"""Direct-fill candidate isolation and source guard rejection, no EDA/hardware."""
from pathlib import Path
import importlib
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


@pytest.fixture(params=[('tile8df9', 9), ('tile8df8', 8)])
def candidate(request):
    name, bits = request.param
    build = importlib.import_module('hdmi_camera_fisheye_' + name + '_build')
    protocol = importlib.import_module('hdmi_camera_fisheye_' + name + '_protocol')
    return name, bits, build, protocol


def test_only_engine_cache_and_equal_byte_constraint_are_replaced(candidate):
    name, bits, build, protocol = candidate
    old = build.read(build.ROOT / 'board/hdmi-camera-fisheye-tile8-build-sources.json')
    current = build.expected_manifest()
    changed = {
        'rtl/experimental/hdmi_camera_fisheye_engine_tile8.v': protocol.CONTRACTS['Engine']['Source'],
        'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v':
            build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'],
        'board/hdmi-camera-fisheye-tile8-internal.fdc': build.FDC,
    }
    assert current['source_files'] == [changed.get(n, n) for n in old['source_files']]
    for source, digest in old['SourceSHA256'].items():
        if source not in changed:
            assert current['SourceSHA256'][source] == digest
    assert build.sha(build.ROOT / build.FDC) == build.sha(build.ROOT / 'board/hdmi-camera-fisheye-tile8-internal.fdc')
    assert current['CSourceDifferenceReview']['CacheIndexBits'] == bits
    assert current['CSourceDifferenceReview']['DirectFillCache'] is True
    assert current['PriorPhysicalProofCountsInherited'] is False


def test_whole_engine_is_exactly_one_index_parameter_change(candidate):
    name, bits, build, protocol = candidate
    baseline = (build.ROOT / 'rtl/experimental/hdmi_camera_fisheye_engine_tile8.v').read_bytes()
    actual = (build.ROOT / protocol.CONTRACTS['Engine']['Source']).read_bytes()
    assert baseline.count(b'.INDEX_BITS(7)') == 1
    assert actual == baseline.replace(b'.INDEX_BITS(7)', ('.INDEX_BITS(' + str(bits) + ')').encode())
    assert protocol.contract('Engine', actual.decode('utf-8-sig'))
    assert protocol.reviewed_candidate_changes({})['Passed'] is True


@pytest.mark.parametrize('old,new', [
    ('wire use_tiles=cfg_corrected;', "wire use_tiles=1'b0;"),
    ('tiled_mode<=use_tiles;', "tiled_mode<=!use_tiles;"),
    ('core_frame_ready && writer_frame_ready', 'core_frame_ready'),
    ('!buffer_valid && !failed', '!failed'),
    ('result_masked ? 24\'d0:result_rgb', 'result_rgb'),
    ('DRAIN: if(writer_done)', 'DRAIN: if(writer_pixels==WIDTH*HEIGHT)'),
    ('if(core_failed || writer_failed)', 'if(core_failed)'),
    ('.frame_tiled(use_tiles)', '.frame_tiled(cfg_corrected^1\'b1)'),
    ('source_end<=29\'h10000000', "source_end<=29'h1fffffff"),
])
def test_changed_mode_pixel_ownership_or_completion_is_rejected(candidate, old, new):
    _, _, build, protocol = candidate
    source = (build.ROOT / protocol.CONTRACTS['Engine']['Source']).read_text(encoding='utf-8-sig')
    assert old in source
    with pytest.raises(ValueError, match='unreviewed complete source'):
        protocol.contract('Engine', source.replace(old, new, 1))


def test_wrong_selected_cache_size_is_rejected(candidate):
    _, bits, build, protocol = candidate
    source = (build.ROOT / protocol.CONTRACTS['Engine']['Source']).read_text(encoding='utf-8-sig')
    with pytest.raises(ValueError, match='unreviewed complete source'):
        protocol.contract('Engine', source.replace('.INDEX_BITS(' + str(bits) + ')', '.INDEX_BITS(7)'))


@pytest.mark.parametrize('old,new', [
    ('assign awvalid=rst_n && state==ADDRESS;', 'assign awvalid=rst_n && state==ADDRESS && !failed;'),
    ('stripe_full[drain_bank]<=0;', 'stripe_full[collect_bank]<=0;'),
    ('if(tiled && read_last)', 'if(tiled && read_enable)'),
    ('DRAIN:if(drain==31)', 'DRAIN:if(drain==0)'),
])
def test_irrevocable_writer_and_last_ram_return_guards_remain(candidate, old, new):
    _, _, build, protocol = candidate
    source = (build.ROOT / protocol.CONTRACTS['Writer']['Source']).read_text(encoding='utf-8-sig')
    assert old in source
    with pytest.raises(ValueError, match='unreviewed complete source'):
        protocol.contract('Writer', source.replace(old, new, 1))


def test_no_old_provider_or_warning_authority_is_selected(candidate):
    name, _, build, protocol = candidate
    for role in ('native', 'scoped_native', 'audit', 'warnings'):
        module = importlib.import_module('hdmi_camera_fisheye_' + name + '_' + role)
        assert module.build is build
        assert Path(module.__file__).name == 'hdmi_camera_fisheye_' + name + '_' + role + '.py'
    warnings = importlib.import_module('hdmi_camera_fisheye_' + name + '_warnings')
    assert warnings.INVENTORY.parent == build.WORK
    assert 'tile8df' in warnings.SCHEMA
    assert warnings.INVENTORY_SHA is None or len(warnings.INVENTORY_SHA) == 64
    assert protocol.release_gate_proof()['AssignmentsChecked'] == 4096
