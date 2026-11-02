"""No hardware: require current session power and exact volatile SRAM Tcl."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_program as program


def test_sram_scripts_use_verified_bit_and_never_flash():
    path=program.prep.WORK/'bit-unused/generate_bitstream/camera720_stats_top.sbit'
    scripts=program.scripts(path)
    assert set(scripts)=={'scan','program'}
    assert path.as_posix() in scripts['program']
    assert 'cfg_program -device_index 0\n' in scripts['program']
    assert 'cfg_read_device_property -mode 3 -device_index 0\n' in scripts['program']
    assert all('flash' not in text.lower() for text in scripts.values())


@pytest.mark.parametrize('powered,notified,timeout',[
    (False,True,90),(True,False,90),(True,True,0),(True,True,301),
    (True,True,float('nan')),(True,True,float('inf')),(True,True,True),
])
def test_invalid_power_notification_or_timeout_rejected_before_hardware(monkeypatch,powered,notified,timeout):
    monkeypatch.setattr(program,'validate',lambda *a:pytest.fail('must reject before validation or hardware'))
    with pytest.raises(ValueError):
        program.execute('unused',board_powered=powered,user_notified=notified,timeout=timeout)


def test_current_session_confirmation_can_be_reused():
    program.execution_authorization(True,True,90)


def test_flash_injection_rejected(monkeypatch):
    monkeypatch.setattr(program.hw,'_scripts',lambda *a:{'scan':'scan','program':'write_flash'})
    with pytest.raises(ValueError,match='SRAM'):program.scripts('unused')


@pytest.fixture
def verified_bit(tmp_path,monkeypatch):
    project=tmp_path/'project';bitwork=project/'bit-a';bitwork.mkdir(parents=True)
    work=project/'program-a';pds=project/'pds';pds.mkdir()
    monkeypatch.setattr(program.prep,'PROJECT',project)
    monkeypatch.setattr(program.prep,'work_path',lambda path:Path(path).resolve())
    monkeypatch.setattr(program.hw,'resolve_pds_bin',lambda path:path)
    def file(name,data='evidence'):
        path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data);return path
    for name in ('pds/cdt_js.exe','pds/cdt_cfg_shell.exe','tools/native_camera_capture.py',
                 'tools/frame_protocol.py','tools/camera_eye_pin_audit.py','bit-a/tool-snapshot.py','bit-a/audited-final.adf'):
        file(name)
    bitpath=file('bit-a/generate_bitstream/camera720_stats_top.sbit')
    evidence=file('bit-a/evidence.json');native=file('bit-a/generate_bitstream/camera720_stats_top.pgr')
    source=file('bound-source.v')
    receipt={'Artifacts':{native.relative_to(bitwork).as_posix():program.sha(native)}}
    file('bit-a/execution-result.json',program.json.dumps(receipt))
    verified={'Verified':True,'Target':program.prep.TARGET,
        'EvidenceSHA256':{'evidence.json':program.sha(evidence)},
        'Bitstream':{'Path':str(bitpath),'SHA256':program.sha(bitpath)},'CandidateADFSHA256':'a'*64}
    monkeypatch.setattr(program.bit,'verify',lambda path:verified)
    monkeypatch.setattr(program.bit,'validate',lambda path:({'InputSHA256':{str(source):program.sha(source)}},
        {'Build':{'PDS':{'Executable':str(pds/'pds_shell.exe')}}}))
    return {'project':project,'bitwork':bitwork,'work':work,'native':native,'source':source}


def test_sram_plan_keeps_all_native_bit_artifacts_in_hash_closure(verified_bit):
    fixture=verified_bit;value,_=program.recipe(fixture['bitwork'],fixture['work'])
    assert value['BoundInputSHA256'][str(fixture['native'])]==program.sha(fixture['native'])
    assert value['BoundInputSHA256'][str(fixture['source'])]==program.sha(fixture['source'])
    assert value['Operation']=='volatile_sram_only'
    assert value['HardwareAccessed'] is False
    assert value['FlashWritten'] is False


def test_native_programming_report_drift_blocks_sram_plan(verified_bit):
    fixture=verified_bit;fixture['native'].write_text('changed after bit verification')
    with pytest.raises(ValueError,match='native bit artifact changed'):
        program.recipe(fixture['bitwork'],fixture['work'])


def test_source_drift_after_plan_validation_stops_before_any_jtag(monkeypatch,verified_bit):
    fixture=verified_bit;value,text=program.recipe(fixture['bitwork'],fixture['work'])
    work=fixture['work'];work.mkdir();path=work/'plan.json';path.write_text('{}')
    for name,content in text.items():(work/(name+'.tcl')).write_bytes(content.encode('utf-8'))
    def validated(plan):
        fixture['source'].write_text('drift after validation')
        return value
    monkeypatch.setattr(program,'validate',validated)
    monkeypatch.setattr(program.hw,'listening_pids',lambda *a:pytest.fail('drift must be rejected before JTAG probe'))
    monkeypatch.setattr(program.hw,'_start_owned',lambda *a:pytest.fail('must not start hardware process'))
    monkeypatch.setattr(program.hw,'_stop_owned',lambda owned:([],[]))
    receipts=[];monkeypatch.setattr(program.hw,'_new_json',lambda path,value:receipts.append(value))
    result=program.execute(path,board_powered=True,user_notified=True,timeout=90)
    assert result['Passed'] is False
    assert result['HardwareAccessed'] is False
    assert result['ProgrammingAttempted'] is False
    assert result['FlashWritten'] is False
    assert 'bound SRAM input drift' in result['Error']
    assert len(receipts)==1
