"""The new cache and sampler must be part of the actual small-system proof."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import hdmi_camera_fisheye_tile8_warnings as w


def test_long_opaque_compiled_path_binds_exact_canonical_key_and_hash():
    plan=w.build.read(w.build.WORK/'build-a/plan.json')
    item=max(plan['CompiledInputs'],key=lambda r:len(r['CompiledPath']))
    path=Path(item['CompiledPath']);assert len(str(path))>260
    watched={};assert w.add(watched,path,item['CompiledSHA256'])==path
    assert watched=={str(path):item['CompiledSHA256']}
    assert w.add(watched,path)==path
    with pytest.raises(ValueError,match='SHA differs'):w.add({},path,'0'*64)
    with pytest.raises(ValueError,match='conflicting'):w.add({str(path):'0'*64},path)
    with pytest.raises(ValueError,match='canonical'):w.add({},path.with_name('not-present.vp'))
    with pytest.raises(ValueError,match='canonical'):w.add({},path.parent/'..'/path.parent.name/path.name)


@pytest.mark.parametrize('change', ['old_system_provider', 'missing_cache', 'different_cache', 'different_sampler','different_arbiter','missing_bank','different_engine','different_writer','mode_flags'])
def test_small_system_binding_rejects_frozen_system_or_wrong_replacement_sources(monkeypatch, tmp_path, change):
    plan = w.build.read(w.build.WORK / 'build-a/plan.json')
    names = {
        'MapperSimulation': (w.build.MAPPER, w.build.ROM, w.build.PROFILE_HEADER, w.build.RADIAL_HEADER),
        'SystemSmallSimulation': (w.build.SAMPLER, w.build.MAPPER, w.build.ROM, w.build.PROFILE_HEADER,
            w.build.RADIAL_HEADER, w.build.REQUIRED_MODULES['ddr_remap_sample_scatter4'],
            w.build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'],
            w.build.REQUIRED_MODULES['ddr_read_arbiter'],
            w.build.REQUIRED_MODULES['hdmi_camera_fisheye_system'],
            w.build.REQUIRED_MODULES['hdmi_camera_fisheye_input_link'],
            w.build.REQUIRED_MODULES['hdmi_camera_fisheye_bank'],w.build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'],
            w.build.REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe']),
        'IOSimulation': (w.build.QUANTIZER, w.build.STATUS_UART, w.build.UART),
    }
    providers = {}; records = {}
    from types import SimpleNamespace
    for kind, sources in names.items():
        receipt = tmp_path / (kind + '.json'); receipt.write_text('{}')
        records[kind] = w.ref(receipt)
        system = kind == 'SystemSmallSimulation'
        hashes = {source if system else str((w.build.ROOT/source).resolve()):
            plan['InputSHA256'][str((w.build.ROOT/source).resolve())] for source in sources}
        result = dict(Passed=True, HardwareAccessed=False, SourceSHA256=hashes,
            Mode='small' if system else 'native', Summary={'CorrectedCoordinates':2073600,'frame_mode_latches':2},
            ActualUARTPinDecodePassed=True, ActualQuantizerAll256ValuesAndTimingPassed=True,
            CandidateEngine=w.build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'],
            CandidateWriter=w.build.REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe'],
            CorrectedCoordinatesTiled8x8=True,RawCoordinatesRaster=True)
        if system:
            if change == 'missing_cache': hashes.pop(w.build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'])
            if change == 'different_cache': hashes[w.build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe']] = '0'*64
            if change == 'different_sampler': hashes[w.build.REQUIRED_MODULES['ddr_remap_sample_scatter4']] = '0'*64
            if change == 'different_arbiter': hashes[w.build.REQUIRED_MODULES['ddr_read_arbiter']] = '0'*64
        if system:
            if change == 'missing_bank': hashes.pop(w.build.REQUIRED_MODULES['hdmi_camera_fisheye_bank'])
            if change == 'different_engine': hashes[w.build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8']] = '0'*64
            if change == 'different_writer': hashes[w.build.REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe']] = '0'*64
            if change == 'mode_flags': result['CorrectedCoordinatesTiled8x8'] = False
        name = {'MapperSimulation':'run_hdmi_camera_fisheye_mapper_sim',
            'SystemSmallSimulation':'run_hdmi_camera_fisheye_tile8_system_sim',
            'IOSimulation':'run_hdmi_camera_fisheye_io_sim'}[kind]
        path = w.SELF.with_name(name+'.py')
        if system and change == 'old_system_provider': path = w.SELF.with_name('run_hdmi_camera_fisheye_system_sim.py')
        providers[name] = SimpleNamespace(__file__=str(path),verify=lambda _, value=result: (value,{}))
    monkeypatch.setattr(w.importlib, 'import_module', lambda name: providers[name])
    with pytest.raises(ValueError, match='provider/receipt reference changed|different current source|frame-locked'):
        w.bind_simulation_receipts({'Simulations':records}, plan, {})
