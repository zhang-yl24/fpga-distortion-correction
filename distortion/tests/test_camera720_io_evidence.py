"""Reject inconsistent native pad parameters and incomplete DVP reports."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_io_evidence as tool


def pins():
    return {'PinInventory':[{'Port':'b_out[0]','VCCIO':'3.3','STANDARD':'LVCMOS33',
        'DRIVE':'8','SLEW':'FAST','LOC':'P19',
        'FinalPrimitiveConnections':[{'NativeInstance':'pad/opit_0'}]}]}


def native_text():
    return '''(ADIF "test"
  (LIBRARY pango_lib
    (CELL gopOBUF_Cell_3 (OPERAREF gopOBUF)
      (PARAMETER VCCIO (DATATYPE STRING) (STRING "3.3"))
      (PARAMETER IOSTANDARD (DATATYPE STRING) (STRING "LVCMOS33"))
      (PARAMETER SLEW_MODE (DATATYPE STRING) (STRING "F"))
      (PARAMETER DRV_CURR_VAL (DATATYPE STRING) (STRING "8"))
      (VIEW OPER (VIEWTYPE OPERATOR))
    )
  )
  (LIBRARY work
    (INSTANCE pad/opit_0 (VIEWREF OPER (CELLREF gopOBUF_Cell_3 (OPERAREF gopOBUF (LIBRARYREF pango_lib))))
      (ATTRIBUTE PAP_IO_LOC (STRING P19))
      (ATTRIBUTE PAP_IO_SLEW (STRING FAST))
      (SITEREF 3 67)
    )
  )
)
'''


def test_native_parameters_override_misleading_functional_defaults(tmp_path):
    path=tmp_path/'route.txt';path.write_text(native_text())
    p=pins();p['PinInventory'][0]['FinalPrimitiveConnections'][0]['FunctionalParameters']={'SLEW_RATE':'"SLOW"'}
    value=tool.io_parameters(path,p)
    assert value['Passed'] and value['Rows'][0]['Parameters']['SLEW_MODE']=='F'
    assert value['HardwareElectricalAcceptance'] is False


@pytest.mark.parametrize('old,new,message',[
    ('(STRING "F")','(STRING "S")','electrical parameter differs'),
    ('(STRING "8")','(STRING "4")','electrical parameter differs'),
    ('(STRING "3.3")','(STRING "1.5")','electrical parameter differs'),
    ('(STRING "LVCMOS33")','(STRING "HSTL15_I")','electrical parameter differs'),
    ('(STRING P19)','(STRING P20)','declared IO attribute differs'),
    ('(INSTANCE pad/opit_0','(INSTANCE wrong/opit_0','incomplete native IO'),
    ('(CELLREF gopOBUF_Cell_3','(CELLREF missing','cell definition missing'),
    ('(SITEREF 3 67)','(PARAMETER SLEW_MODE (DATATYPE STRING) (STRING "S"))','override unreviewed'),
])
def test_native_electrical_mismatch_rejected(tmp_path,old,new,message):
    path=tmp_path/'route.txt';path.write_text(native_text().replace(old,new))
    with pytest.raises(ValueError,match=message):tool.io_parameters(path,pins())


def test_native_dump_truncation_and_duplicate_parameter_rejected(tmp_path):
    path=tmp_path/'route.txt';path.write_text(native_text()[:-3])
    with pytest.raises(ValueError,match='incomplete'):tool.io_parameters(path,pins())
    duplicate='(PARAMETER SLEW_MODE (DATATYPE STRING) (STRING "F"))'
    path.write_text(native_text().replace(duplicate,duplicate+'\n'+duplicate))
    with pytest.raises(ValueError,match='ambiguous'):tool.io_parameters(path,pins())


def dvp(port='cam_data[0]',kind='min',corner='fast',slack=.123):
    return f'''Startpoint : {port} (port)
Endpoint : system/input_link/input_dma/capture/first_byte[0]/opit_0/D
Path Type : {kind} ({corner} corner)
Path Class : sequential timing path
 Clock camera_pclk (rising edge) 0.000 0.000
 Input external delay {5.0 if kind=='max' else 0.0:.3f} 0.000
 Clock camera_pclk (rising edge) 20.833 20.833
 Slack ({'MET' if slack>=0 else 'VIOLATED'}) {slack:.3f}
'''


def test_dvp_requires_every_input_corner_and_kind(tmp_path):
    path=tmp_path/'report.rtr'
    rows=[dvp(p,t,c) for p in sorted(tool.PORTS) for t in ('min','max') for c in ('slow','fast')]
    path.write_text(''.join(rows));value=tool.dvp_summary(tool.dvp_records([path]))
    assert value['ReportedBudgetCoverageComplete'] and value['CoveredCases']==40
    assert not value['AllFanoutPathsEnumerated'] and not value['ExternalTimingAccepted']
    path.write_text(''.join(rows[:-1]));value=tool.dvp_summary(tool.dvp_records([path]))
    assert not value['ReportedBudgetCoverageComplete'] and len(value['MissingCases'])==1


@pytest.mark.parametrize('old,new,message',[
    ('Slack (MET) 0.123','Slack (VIOLATED) -0.123','timing violation'),
    ('Input external delay 0.000','Input external delay -1.000','external budget differs'),
    ('Clock camera_pclk (rising','Clock pixel_clk (rising','sampling clock/edge differs'),
    ('system/input_link/input_dma/capture/','unexpected_hierarchy/','escaped reviewed hierarchy'),
    ('Path Class : sequential timing path','Path Class : combinational timing path','not sequential'),
    ('Path Class : sequential timing path','Path Class : sequential timing path\nTiming Exception : False Path','unexpectedly excepted'),
])
def test_dvp_wrong_budget_domain_exception_or_failure_rejected(tmp_path,old,new,message):
    path=tmp_path/'report.rtr';path.write_text(dvp().replace(old,new))
    with pytest.raises(ValueError,match=message):tool.dvp_records([path])


def test_dvp_truncated_last_path_rejected(tmp_path):
    path=tmp_path/'report.rtr';path.write_text(dvp().split(' Slack')[0])
    with pytest.raises(ValueError,match='incomplete'):tool.dvp_records([path])


def test_input_hash_merge_does_not_overwrite_drift(tmp_path):
    path=tmp_path/'receipt.json';path.write_text('original');watched={}
    tool.watch(watched,path);path.write_text('mutated')
    with pytest.raises(ValueError,match='drift'):tool.watch(watched,path)


def test_output_file_accepts_json_and_rejects_reuse_or_escape(tmp_path,monkeypatch):
    work=tmp_path/'720';work.mkdir();stage=work/'io-final-a';stage.mkdir()
    monkeypatch.setattr(tool.prep,'WORK',work)
    path=stage/'proof.json';assert tool.output_file(path)==path
    path.write_text('keep')
    with pytest.raises(ValueError,match='fresh IO output'):tool.output_file(path)
    with pytest.raises(ValueError,match='fresh IO output'):tool.output_file(tmp_path/'outside.json')
