"""Independent layout/priority checks plus saved actual peer XSim evidence."""
from pathlib import Path
import hashlib
import json
import re
import sys

import pytest

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK.parents[1] / 'tools'))
import hdmi_camera_fisheye_directfill_contract as contract


def source_layout(text):
    # This parser accepts only the four observed explicit concatenations. It is
    # deliberately a source-specific check, not general RTL or native mapping.
    flat = contract.compact(text)
    for parity in ('even', 'odd'):
        for half in ('a', 'b'):
            name = 'fill_' + parity + '_' + half
            matches = re.findall(r'wire\[63:0\]' + name + r'=\{([^{}]+)\};', flat)
            if len(matches) != 1:
                raise ValueError('one explicit parity/half payload required')
            slices = re.findall(r'fill_sixteen\[(\d+):(\d+)\]', matches[0])
            if len(slices) != 4 or ','.join('fill_sixteen[' + a + ':' + b + ']' for a, b in slices) != matches[0]:
                raise ValueError('only four complete RGB565 words in each payload')
            observed = []
            for hi, lo in reversed(slices):
                hi, lo = int(hi), int(lo)
                if hi - lo != 15 or lo % 16:
                    raise ValueError('unaligned RGB565 word')
                observed.append(lo // 16)
            expected = [2 * lane + (1 if parity == 'odd' else 0) + (8 if half == 'b' else 0)
                        for lane in range(4)]
            if observed != expected:
                raise ValueError('linear pixel/parity/RAM-lane mapping differs')
    for suffix, bit in (('a', '0'), ('b', '1')):
        if f"write_address_{suffix}={{write_commit_line,write_commit_beat,1'b{bit}}};" not in flat:
            raise ValueError('owned line/beat/half address differs')


def test_independent_layout_of_every_word_and_parity_is_correct():
    source_layout(contract.SOURCE.read_text())


@pytest.mark.parametrize('before,after', [
    ('fill_sixteen[111:96],fill_sixteen[79:64]', 'fill_sixteen[79:64],fill_sixteen[111:96]'),
    ('fill_sixteen[15:0]', 'fill_sixteen[31:16]'),
    ('fill_sixteen[255:240]', 'fill_sixteen[239:224]'),
    ('fill_sixteen[143:128]', 'fill_sixteen[142:127]'),
    ("write_commit_beat,1'b0", "write_commit_beat,1'b1"),
    ('{write_commit_line,write_commit_beat', '{selected_line,write_commit_beat'),
    ('fill_sixteen[239:224]', 'rdata[239:224]'),
])
def test_independent_layout_negative_cases_do_not_rely_on_whole_source_sha(before, after):
    source = contract.SOURCE.read_text()
    assert source.count(before) >= 1
    with pytest.raises(ValueError):
        source_layout(source.replace(before, after, 1))


def test_registered_fields_capture_and_priority_live_in_the_same_main_clock_block():
    source = contract.compact(contract.SOURCE.read_text())
    main = source[source.rindex('always@(posedgeclk)begin'):source.rindex('endmodule')]
    assert main.index('if(!rst_n)begin') < main.index('case(state)')
    assert main.index('WAIT_COMMIT:beginif(write_commit_last)') < main.index('endcase') < main.index('if(!failed&&rvalid)begin')
    assert main.count('fill_write_valid<=1;') == 1
    receive = main[main.index('if(!failed&&rvalid)begin'):main.index('if(!failed&&&watchdog')]
    assert 'if(!receiving)beginfailed<=1;fault<=8\'h04;state<=FAULT;valid_lines[selected_line]<=0;' in receive
    assert 'fill_write_valid<=1;fill_write_beat<=fill_beat;fill_write_line<=selected_line;fill_write_block<=selected_block;' in receive
    # selected line/block are written only in SELECT; they cannot change while
    # AR/FILL/WAIT_COMMIT owns this transaction, including an illegal ninth R.
    selected = re.findall(r'selected_line<=([^;]+);', main)
    block = re.findall(r'selected_block<=([^;]+);', main)
    assert selected == ['0', 'selected_number[7+:INDEX_BITS]']
    assert block == ['0', 'selected_number[31:7]']


def test_contract_rejects_fault_block_relocated_before_same_edge_publication(monkeypatch):
    source = contract.SOURCE.read_text()
    start = source.index('            if(!failed && rvalid)begin')
    end = source.index('            if(!failed && &watchdog', start)
    fault = source[start:end]
    changed = source[:start] + source[end:]
    start_case = changed.index('            case(state)')
    changed = changed[:start_case] + fault + changed[start_case:]
    monkeypatch.setattr(contract, 'SOURCE_SHA256', hashlib.sha256(changed.encode()).hexdigest())
    with pytest.raises(ValueError) as error:
        contract.review_source(changed)
    assert 'complete pinned direct-fill source SHA256' not in str(error.value)


def test_actual_peer_xsim_receipt_and_poisoned_payload_edge_cases_are_complete():
    path = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a') / 'cache-commit-collision-a/simulation.json'
    value = json.loads(path.read_text())
    assert value['Passed'] is True and value['InputDrift'] == []
    assert value['HDLSimulationExecuted'] is True and value['PDSAccessed'] is False and value['HardwareAccessed'] is False
    assert value['SourceSHA256'][str(contract.SOURCE)] == contract.SOURCE_SHA256
    assert value['Summary']['Cases'] == value['Summary']['SuccessfulCommonResetRecoveries'] == 4
    assert value['Summary']['IndependentRAMPixelsChecked'] == 864
    for name, digest in value['SourceSHA256'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest
    for name, digest in value['ArtifactsSHA256'].items():
        assert hashlib.sha256((path.parent / name).read_bytes()).hexdigest() == digest
    bench = Path(next(name for name in value['SourceSHA256'] if name.endswith('.sv'))).read_text()
    assert 'rdata=~payload(number)' in bench and 'pattern_salt=pattern_salt+1' in bench
    assert 'rdata={256{1\'b1}}' in bench and 'last_words_unchanged()' in bench


def test_actual_original_contract_bind_keeps_source_only_acceptance_limits():
    facts, watched = contract.review()
    assert facts['ChecksUseOnlyPinnedSourceAndSavedUnitEvidence'] is True
    assert facts['OnlyActualFinalRAMCommitPublishesTagAndValid'] is True
    assert facts['RawProtocolFaultInvalidationHasFinalAssignmentPriority'] is True
    assert facts['RAMMappingAccepted'] is facts['NativeEquivalent'] is facts['CDCAccepted'] is facts['STAInherited'] is False
    assert facts['HardwareReleaseAllowed'] is False
    assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest for name, digest in watched.items())
