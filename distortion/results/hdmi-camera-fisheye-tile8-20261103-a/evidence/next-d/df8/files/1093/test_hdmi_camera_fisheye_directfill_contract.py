"""CPU-only adversarial checks of the finite direct-fill source/evidence contract."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import hdmi_camera_fisheye_directfill_contract as contract


@pytest.fixture
def source():
    return contract.SOURCE.read_bytes().decode('utf-8')


def replace_once(source, before, after):
    assert source.count(before) >= 1, before
    changed = source.replace(before, after, 1)
    assert changed != source
    return changed


def test_actual_source_and_complete_saved_unit_closure_are_bound():
    facts, watched = contract.review(contract.SOURCE)
    assert facts['Passed'] and facts['SourceSHA256'] == contract.SOURCE_SHA256
    assert facts['CompletedUnitReceipt']['SHA256'] == contract.UNIT_RECEIPT_SHA256
    assert facts['RegisteredRAMWriteEnable']
    assert facts['OnlyActualFinalRAMCommitPublishesTagAndValid']
    assert facts['RawProtocolFaultInvalidationHasFinalAssignmentPriority']
    assert len(facts['PreservedBaselineSections']) == 8
    assert set(facts['SavedUnitCases']) == {'639-i3', '1920-i7', '1920-i8', '1920-i9'}
    for path in (contract.SOURCE, contract.BASELINE, contract.BENCH, contract.RUNNER,
                 contract.UNIT_RECEIPT, contract.SELF):
        assert str(path.resolve()) in watched
    assert len(watched) >= 20
    assert all(facts[key] is False for key in ('RAMMappingAccepted', 'NativeEquivalent',
               'CDCAccepted', 'STAInherited', 'HardwareReleaseAllowed', 'PDSAccessed', 'HardwareAccessed'))


MUTATIONS = (
    ('raw_rvalid_ce', 'wire write_commit=rst_n && !failed && fill_write_valid;',
     'wire write_commit=rst_n && !failed && rvalid;'),
    ('raw_rid_ce', 'wire write_commit=rst_n && !failed && fill_write_valid;',
     'wire write_commit=rst_n && !failed && fill_write_valid && rid==0;'),
    ('early_valid', 'if(write_commit_last)begin', 'if(fill_beat==7)begin'),
    ('sixth_beat_last', 'write_commit && fill_write_beat==7;', 'write_commit && fill_write_beat==6;'),
    ('raw_payload_ram', 'wire [255:0] fill_sixteen=fill_write_data;', 'wire [255:0] fill_sixteen=rdata;'),
    ('payload_ce', 'always @(posedge clk)fill_write_data<=rdata;',
     'always @(posedge clk)if(rvalid)fill_write_data<=rdata;'),
    ('payload_reset', 'always @(posedge clk)fill_write_data<=rdata;',
     'always @(posedge clk)if(!rst_n)fill_write_data<=0;else fill_write_data<=rdata;'),
    ('line_from_live_request', 'fill_write_line<=selected_line;', 'fill_write_line<=pixel_number[0][7 +: INDEX_BITS];'),
    ('beat_from_next_cycle', 'fill_write_beat<=fill_beat;', "fill_write_beat<=fill_beat+1'b1;"),
    ('block_from_live_query', 'fill_write_block<=selected_block;', 'fill_write_block<=pixel_number[0][31:7];'),
    ('line_wrong_commit', '{write_commit_line,write_commit_beat,1\'b0}',
     '{selected_line,write_commit_beat,1\'b0}'),
    ('tag_wrong_commit', 'tags[write_commit_line]<=fill_write_block;',
     'tags[write_commit_line]<=selected_block;'),
    ('rid_fault_removed', 'rid!=0 || rlast!=(fill_beat==7)', 'rlast!=(fill_beat==7)'),
    ('early_last_accepted', 'rlast!=(fill_beat==7)', 'rlast && fill_beat!=7'),
    ('unsolicited_return_accepted', 'if(!receiving)begin failed<=1;',
     'if(!receiving && address_pending)begin failed<=1;'),
    ('protocol_invalidation_removed', "state<=FAULT;valid_lines[selected_line]<=0;end\n                else if(rid!=0",
     "state<=FAULT;end\n                else if(rid!=0"),
    ('stage_not_reset', 'fill_beat<=0;fill_write_valid<=0;fill_write_beat<=0;',
     'fill_beat<=0;fill_write_beat<=0;'),
    ('sticky_fault_not_reset', 'watchdog<=0;failed<=0;fault<=0;', 'watchdog<=0;fault<=0;'),
    ('stage_retains_valid', 'fill_write_valid<=0;\n            // Same-cycle', '// Same-cycle'),
    ('early_metadata_write', 'fill_write_valid<=1;', 'fill_write_valid<=1;valid_lines[selected_line]<=1;'),
    ('ram_wrong_port_owner', 'if(write_commit)even_pixels[even_a]', 'if(rvalid)even_pixels[even_a]'),
    ('new_frame_not_invalidated', 'begin base<=frame_base;valid_lines<=0;frame_loaded<=1;end',
     'begin base<=frame_base;frame_loaded<=1;end'),
    ('admission_looks_through_full_fifo', 'queue_count<2;', 'queue_count<2 || pop;'),
    ('new_frame_overrides_pending_query', 'frame_valid && queue_empty', 'frame_valid'),
    ('raw_rvalid_hits_counter', 'pending_hits<=hit_increment;', 'pending_hits<=hit_increment+rvalid;'),
    ('hit_count_bypass_removed', "committed_hits+{29'd0,pending_hits}", 'committed_hits'),
    ('partial_output_on_failure', 'assign out_valid=!failed && (v1 || state==RESULT);',
     'assign out_valid=v1 || state==RESULT;'),
    ('frame_ready_omits_registered_query', '&& !pre_valid && !query_valid && !failed;',
     '&& !pre_valid && !failed;'),
    ('failure_auto_recovers', 'FAULT:state<=FAULT;', 'FAULT:state<=IDLE;'),
    ('no_return_timeout_removed', 'if(!failed && &watchdog && !progress && (state==AR || state==FILL))begin',
     'if(1\'b0)begin'),
)


@pytest.mark.parametrize('name,before,after', MUTATIONS, ids=[row[0] for row in MUTATIONS])
def test_critical_mutants_fail_structural_checks_even_if_whole_file_pin_is_replaced(
        source, monkeypatch, name, before, after):
    changed = replace_once(source, before, after)
    # Exercise the independent finite clauses/unchanged baseline sections, not
    # merely the final whole-file hash failure that would also reject each edit.
    monkeypatch.setattr(contract, 'SOURCE_SHA256', hashlib.sha256(changed.encode()).hexdigest())
    with pytest.raises(ValueError) as error:
        contract.review_source(changed)
    assert 'complete pinned direct-fill source SHA256' not in str(error.value), name


@pytest.mark.parametrize('extra', ['\n', '\n// caller-supplied unreviewed revision\n',
                                  '\nmodule hidden_owner; endmodule\n'])
def test_complete_file_pin_rejects_unreviewed_changes(source, extra):
    with pytest.raises(ValueError, match='complete pinned direct-fill source SHA256'):
        contract.review_source(source + extra)


@pytest.mark.parametrize('bad', [None, b'module x;', 123, ['module x;']])
def test_only_a_complete_string_is_reviewable(bad):
    with pytest.raises(ValueError, match='complete string'):
        contract.review_source(bad)


def test_missing_or_modified_selected_source_is_rejected(source, tmp_path):
    with pytest.raises(ValueError, match='missing direct-fill contract input'):
        contract.review(tmp_path / 'missing.v')
    changed = tmp_path / 'modified.v'
    changed.write_text(source + '\n', encoding='utf-8')
    with pytest.raises(ValueError, match='SHA drift'):
        contract.review(changed)


@pytest.mark.parametrize('field,bad', [('Passed', False), ('PDSAccessed', True),
    ('HardwareAccessed', True), ('FullFrameSimulated', True), ('InputDrift', ['cache.v']),
    ('SingleRegisteredBeatPerWrite', False), ('PostReceiveScatterCycles', 8)])
def test_saved_receipt_does_not_confer_unperformed_acceptance(field, bad, monkeypatch, tmp_path):
    value = json.loads(contract.UNIT_RECEIPT.read_text())
    value[field] = bad
    path = tmp_path / 'simulation.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    monkeypatch.setattr(contract, 'UNIT_RECEIPT', path)
    monkeypatch.setattr(contract, 'UNIT_RECEIPT_SHA256', contract.sha(path))
    with pytest.raises(ValueError, match='clean completed direct-fill cache unit receipt'):
        contract.review()


def test_saved_unit_artifact_bytes_are_rechecked(monkeypatch, tmp_path):
    original = contract.UNIT_RECEIPT
    value = json.loads(original.read_text())
    path = tmp_path / 'simulation.json'
    shutil.copyfile(original, path)
    for name in value['ArtifactsSHA256']:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original.parent / name, tmp_path / name)
    (tmp_path / 'summary-1920-i9.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(contract, 'UNIT_RECEIPT', path)
    with pytest.raises(ValueError, match='SHA drift'):
        contract.review()
