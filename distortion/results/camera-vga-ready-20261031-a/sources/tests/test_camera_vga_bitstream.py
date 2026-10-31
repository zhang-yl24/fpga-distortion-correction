from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera_vga_bitstream as bit


def test_actual_camera_closure_and_final_proof():
    original,watched=bit.authority()
    assert len(original['InputSHA256'])==115
    assert len(original['CompiledInputs'])==109
    assert watched[bit.ADF]==bit.ADF_SHA
    assert watched[bit.AUDIT]==bit.AUDIT_SHA
    assert not bit.core.check_inputs(watched)


def test_direct_context_has_single_fresh_sta_then_gate_then_bit():
    original=bit.load(bit.BASE/'plan.json')
    work=bit.BUILD/'bit-render-test'
    text=bit.render_tcl((bit.BASE/'timing.tcl').read_text(encoding='ascii'),original['AliasWorkDirectory'],work)
    assert text.count('report_timing -force_to_run')==1
    assert 'mpnr_report_timing' not in text and 'P:/' not in text
    assert text.index('report_timing -force_to_run')<text.index('--gate')<text.index('gen_bit_stream')
    assert text.count('-input_db_file {'+work.as_posix()+'/audited-final.adf}')==2
    assert 'compile -top_module camera_vga_output_top' in text
    assert '-scbv {High Voltage} -unused_io_status UNUSED' in text


def events():
    return '\n'.join(['Process "Report Timing" started.','Process "Report Timing" done.',bit.MARKER,
                      'Process "Generate Bitstream" started.','Process "Generate Bitstream" done.',bit.COMPLETE])


def test_native_event_order_is_exact():
    assert len(bit.actual_events(events()))==6


@pytest.mark.parametrize('text',[
    events().replace(bit.MARKER,''),
    events().replace('Process "Report Timing" done.','Process "Synthesize" started.'),
    events().replace(bit.MARKER,bit.MARKER.replace(bit.ADF_SHA,'0'*64)),
    events().replace('Process "Generate Bitstream" started.', 'Process "Generate Bitstream" started.\nProcess "Report Timing" started.'),
])
def test_event_or_gate_omission_rejected(text):
    with pytest.raises(ValueError):bit.actual_events(text)


def header(target=bit.TARGET):
    data=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    for tag,value in zip(b'abcdef',(target,'Logos2-PG2L100H--6-FBG676','2026/10/31','12:00:00','Fabric Compiler','2023.2-SP3<154097>')):
        raw=value.encode()+b'\0';data+=bytes([tag])+len(raw).to_bytes(2,'big')+raw
    return data+b'ghi'+b'\0'*1000001


def test_camera_bit_header_has_exact_top():
    assert bit.bit_header(header())['Design']==bit.TARGET
    with pytest.raises(ValueError):bit.bit_header(header('processed_output_top'))
    with pytest.raises(ValueError):bit.bit_header(header()[:300])


def test_camera_only_direct_bit_work_root():
    for path in (bit.BUILD/'nested/bit-new',bit.PROJECT/'build/processed-output/bit-new',bit.BUILD/'program-new'):
        with pytest.raises(ValueError):bit.work_path(path,exists=False)
    assert bit.work_path(bit.BUILD/'bit-cpu-scope-test',exists=False).parent==bit.BUILD
