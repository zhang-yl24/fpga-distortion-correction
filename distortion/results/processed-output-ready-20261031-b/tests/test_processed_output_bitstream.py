"""Focused guards for the offline final-ADF export recipe and its gate order."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import processed_output_bitstream as tool


def native_log():
    return '\n'.join([
        'Process "Report Timing" started.', 'Process "Report Timing" done.',
        tool.MARKER, 'Process "Generate Bitstream" started.',
        'Process "Generate Bitstream" done.', tool.COMPLETE])


def test_exact_runtime_order():
    assert len(tool.actual_events(native_log())) == 6


@pytest.mark.parametrize('text', [
    native_log().replace(tool.MARKER, ''),
    native_log().replace(tool.MARKER, tool.MARKER + 'wrong'),
    'Process "Compile" started.\n' + native_log(),
    native_log().replace('Process "Report Timing" done.', ''),
    native_log().replace('Process "Generate Bitstream" started.', 'Process "Place and Route" started.'),
    native_log().replace(tool.COMPLETE, ''),
    native_log().replace(tool.MARKER, '') + '\n' + tool.MARKER,
])
def test_missing_or_reordered_actual_stage_rejected(text):
    with pytest.raises(ValueError):
        tool.actual_events(text)


def bit(design=tool.TARGET, device='Logos2-PG2L100H--6-FBG676'):
    data = bytes.fromhex('00090ff00ff00ff00ff000') + b'PANGO MICROSYSTEMS, INC.\0\1'
    values = [design,device,'2026/10/31','03:00:00','Fabric Compiler','2023.2-SP3<154097>']
    for tag,value in zip(b'abcdef',values):
        text = value.encode() + b'\0'
        data += bytes([tag]) + len(text).to_bytes(2,'big') + text
    return data + b'ghi' + b'\x00' * 1000001


def test_header_exact_candidate_identity():
    assert tool.bit_header(bit())['Design'] == tool.TARGET


@pytest.mark.parametrize('data', [bit('wrong'),bit(device='wrong'),bit()[:60],bit()[:300],b'wrong'])
def test_wrong_or_truncated_bit_rejected(data):
    with pytest.raises(ValueError):
        tool.bit_header(data)


def test_render_keeps_context_and_gates_explicit_final_adf():
    original = (tool.BASE/'timing.tcl').read_text(encoding='ascii')
    plan = tool.load(tool.BASE/'plan.json')
    alias = 'P:/distortion/build/processed-output/bit-unit'
    text = tool.render_tcl(original,plan['AliasWorkDirectory'],alias)
    assert text.count('gen_bit_stream ') == 1
    assert text.index('--gate {') < text.index('gen_bit_stream ')
    assert text.count('-input_db_file {'+alias+'/audited-final.adf}') == 2
    assert 'gen_netlist' not in text
    assert '-unused_io_status UNUSED' in text


def test_changed_context_tail_is_rejected():
    original = (tool.BASE/'timing.tcl').read_text(encoding='ascii')
    plan = tool.load(tool.BASE/'plan.json')
    with pytest.raises(ValueError):
        tool.render_tcl(original.replace('-max_path 20','-max_path 21'),
                        plan['AliasWorkDirectory'],'P:/distortion/build/processed-output/bit-unit')
