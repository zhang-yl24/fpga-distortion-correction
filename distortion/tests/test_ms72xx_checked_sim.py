from pathlib import Path
import csv
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_ms72xx_checked_sim as runner


def test_exact_tx_copy_preserves_reference_commands_and_wait():
    result = runner.audit_tx_copy(runner.ROOT / runner.SOURCES[4], runner.ROOT / runner.RTL[1])
    assert result['ExactTransformationVerified']
    assert result['CommandRowsUnchanged'] == 49
    assert result['OriginalWaitPreserved']


@pytest.mark.parametrize('old,new', [("22'h30D399", "22'h30D398"),
                                     ("16'h1281,8'h04", "16'h1281,8'h05"),
                                     ("dri_cnt != 5'd18", "dri_cnt != 5'd17")])
def test_unapproved_tx_modifications_rejected(tmp_path, old, new):
    source = (runner.ROOT / runner.RTL[1]).read_text(encoding='utf-8')
    assert old in source
    target = tmp_path / 'changed.v'
    target.write_text(source.replace(old, new, 1), encoding='utf-8')
    with pytest.raises(ValueError, match='exact allowed'):
        runner.audit_tx_copy(runner.ROOT / runner.SOURCES[4], target)


def test_reference_drift_is_rejected_before_transform(tmp_path):
    target = tmp_path / 'reference.v'
    target.write_bytes((runner.ROOT / runner.SOURCES[4]).read_bytes() + b' ')
    with pytest.raises(ValueError, match='SHA256'):
        runner.audit_tx_copy(target, runner.ROOT / runner.RTL[1])


def write_trace(path, rows):
    with path.open('w', encoding='ascii', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['scenario','request','device','read','addr','data','response','nack'])
        for scenario,request,device,read,address,data,response,nack in rows:
            writer.writerow([scenario,request,f'{device:02x}',read,f'{address:04x}',
                             f'{data:02x}',f'{response:02x}',nack])


def test_all_seven_ordered_wire_scenarios_are_checked(tmp_path):
    target = tmp_path / 'trace.csv'
    rows = runner.expected_wire_trace()
    write_trace(target, rows)
    result = runner.validate_wire_trace(target)
    assert result['Transactions'] == 2117
    assert result['ScenarioCounts'] == [372,1,317,318,368,369,372]
    assert result['StickyObservationConfigCycles'] == 40


@pytest.mark.parametrize('mutation', ['missing','reorder','duplicate','wrong_nack','ghost_tx','wrong_read'])
def test_trace_mutations_rejected(tmp_path, mutation):
    rows = runner.expected_wire_trace()
    if mutation == 'missing':
        rows.pop(4)
    elif mutation == 'reorder':
        rows[10], rows[11] = rows[11], rows[10]
    elif mutation == 'duplicate':
        rows.append(rows[-1])
    elif mutation == 'wrong_nack':
        rows[372] = (*rows[372][:-1], 0)
    elif mutation == 'ghost_tx':
        rows[339] = rows[338]
    else:
        row = list(rows[1]); row[-2] = 0; rows[1] = tuple(row)
    target = tmp_path / 'bad.csv'
    write_trace(target, rows)
    with pytest.raises(ValueError, match='ordered wire trace'):
        runner.validate_wire_trace(target)


def test_rx_transform_is_bound_to_original_not_self_oracle():
    result = runner.edid.audit_controller(runner.ROOT / runner.RTL[0], runner.ROOT / runner.SOURCES[5])
    assert result['OnlyEDIDBytesChanged']
    assert result['ReferenceSHA256'] == runner.edid.REFERENCE_SHA256
    assert 'tools/board1080_edid.py' in runner.SOURCES


def test_mock_and_wire_compilation_sources_remain_explicit():
    assert runner.RTL[-1] == 'tests/tb_ms72xx_checked_ctl.sv'
    assert all('platform/video_base/source/hdmi/iic_dri.v' != source for source in runner.SOURCES)

