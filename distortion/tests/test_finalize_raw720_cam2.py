"""Four focused rejection tests for the narrow post-build exception policy."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import finalize_raw720_cam2 as f

WORK=f.APPROVED/'synthetic-post-finalizer-no-directory-created'

def stdout():
    marker=f"Analyzing project file '{(WORK/(f.TARGET+'.pds')).as_posix()}'."
    commands=[f'compile -top_module {f.TARGET}','synthesize -ads -selected_syn_tool_opt 2','dev_map',
        'pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE',
        'report_timing -max_path 5','gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED']
    return '\n'.join(f.expected_prefix_errors()+[marker,f'Executing : add_design {(f.b.ROOT/"rtl/raw_camera_capture.v").as_posix()}',
        *['Executing : '+command+' successfully.' for command in commands],
        f'The bitstream file is "{(WORK/f"generate_bitstream/{f.TARGET}.sbit").as_posix()}"'])

def test_unrecognized_prefix_path_or_gate_line_rejected():
    good=stdout();assert f.audit_runtime_log(good,b'',WORK)['RuntimeErrors']==0
    for bad in [good.replace('E: Missing final timing report','E: unexpected source compile failure'),
        good.replace('board/report_timing/','board/another_target/'),good.replace('at line 38.','at line 37.')]:
        with pytest.raises(ValueError,match='prefix'):f.audit_runtime_log(bad,b'',WORK)

def test_even_known_error_after_flow_is_fatal():
    for bad in [stdout()+'\nE: Missing final timing report\n',stdout()+'\nERROR: source failed\n']:
        with pytest.raises(ValueError,match='actual-flow'):f.audit_runtime_log(bad,b'',WORK)
    with pytest.raises(ValueError,match='stderr'):f.audit_runtime_log(stdout(),b'E: bad',WORK)

def test_other_native_failure_or_boolean_exit_rejected():
    result={'Target':f.TARGET,'Passed':False,'HardwareAccessed':False,'ProcessExitCode':0,'Error':f.ORIGINAL_ERROR,
        'StartedUtc':'2026-10-26T15:00:00+00:00','EndedUtc':'2026-10-26T15:01:00+00:00'}
    assert f.audit_native_result(result)[1]>f.audit_native_result(result)[0]
    for change in [{'ProcessExitCode':1},{'ProcessExitCode':False},{'Passed':True},{'Error':'other PDS error'}]:
        with pytest.raises(ValueError):f.audit_native_result({**result,**change})

def test_final_timing_db_and_temporal_order_rejected():
    text=f'Design Summary : All Constraints Met.\n{WORK/f"place_route/{f.TARGET}_pnr.adf"}\n'
    f.audit_final_timing(text,WORK,2,3,4,1,5)
    for bad in [text.replace('All Constraints Met.','Some Constraints Violated.'),text+text,
        text.replace('_pnr.adf','_other_db.adf')]:
        with pytest.raises(ValueError):f.audit_final_timing(bad,WORK,2,3,4,1,5)
    with pytest.raises(ValueError,match='order'):f.audit_final_timing(text,WORK,3,2,4,1,5)
