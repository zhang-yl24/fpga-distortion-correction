"""Only local negative/source-family checks while final v3 pins remain pending."""
from pathlib import Path
import ast
import json
import pytest
import assemble_stage_d_c as a


def test_pending_v3_manifest_cannot_prepare_or_write_an_archive(tmp_path,monkeypatch):
    monkeypatch.setattr(a.authority,'PROVIDER_SHA256',None)
    request={'Schema':a.SCHEMA,'Candidate':'df8','Repository':str(tmp_path),
             'BasePackage':str(tmp_path/'base'),'DestinationPackage':str(tmp_path/'destination'),
             'Roles':{},'AdditionalFiles':[]}
    config=tmp_path/'unit-request.json';config.write_text(json.dumps(request))
    with pytest.raises(ValueError,match='not frozen'):a.assemble(config)
    assert not (tmp_path/'destination').exists()


@pytest.mark.parametrize('schema',['hdmi-camera-fisheye-tile8df8v2-bitstream-execution-v1',
                                  'tile8df8-application-query-diagnostic-execution-v1'])
def test_earlier_or_diagnostic_execution_never_substitutes_for_v3(schema):
    with pytest.raises(ValueError):a.check_bit_execution({'Schema':schema})


def test_new_c_keeps_d_wire_analyzer_and_original_source_contract_pins():
    assert a.FPS_REVIEWER_SHA=='1599309e9b8a6e9db305858774d08972ce1b59b794d196393673956a1a1032f9'
    assert a.PORTABLE_SHA=='df228ebd19c15ab4281f329bfb8c595d22e0595775f238fe24440be9837e319a'
    assert a.portable.CANDIDATES['df8']['SourceSHA256']=='d4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e'
    assert a.portable.CANDIDATES['df8']['UnitWork']=='work/hdmi-camera-fisheye-tile8df9-20261103-a/cache-unit-a'


def test_c_authority_does_not_call_d_v2_metadata_or_provider_verification():
    tree=ast.parse(Path(a.__file__).read_text(encoding='utf-8'))
    calls=[node.func for node in ast.walk(tree) if isinstance(node,ast.Call)]
    assert not any(isinstance(f,ast.Attribute) and f.attr in ('verify','audit_request','release_metadata') for f in calls)
    assert {'OriginalProviderManifest','OriginalRootSourceReview'} <= a.ROLES


@pytest.mark.parametrize('mutation',['oldschema','oldbitdir','oldprogramdir'])
def test_program_family_is_v3_only(mutation,tmp_path):
    work=tmp_path/'work'
    plan={'Schema':'hdmi-camera-fisheye-tile8df8v3-sram-plan-v1','Target':a.TARGET,
          'WorkDirectory':str(work/'program-v3-a'),'BitstreamWorkDirectory':str(work/'bit-v3-a')}
    program={'Target':a.TARGET,'WorkDirectory':str(work/'program-v3-a')}
    if mutation=='oldschema':plan['Schema']=plan['Schema'].replace('v3','v2')
    elif mutation=='oldbitdir':plan['BitstreamWorkDirectory']=str(work/'bit-v2-a')
    else:program['WorkDirectory']=str(work/'program-v2-a')
    with pytest.raises(ValueError,match='exact SRAM schema'):
        a.check_program_identity(plan,program,work,tmp_path/'not-a-bit','a'*64,lambda *args:None)


def program_fragment(tmp_path):
    work=tmp_path/'local-unit-work';directory=work/'program-v3-a';directory.mkdir(parents=True)
    selected=work/'bit-v3-a/generate_bitstream/hdmi_camera_fisheye_top.sbit'
    plan={'Schema':'hdmi-camera-fisheye-tile8df8v3-sram-plan-v1','Target':a.TARGET,
          'WorkDirectory':str(directory),'BitstreamWorkDirectory':str(work/'bit-v3-a'),
          'CableIndex':0,'Frequency':'1MHz','ServerPort':65420,'RequiresExplicitExecute':True,
          'RequiresCurrentSessionBoardPower':True,'UserMustBeNotifiedBeforeExecution':True,'Tcl':{}}
    program={'Target':a.TARGET,'WorkDirectory':str(directory),'ExecutorSHA256':'a'*64,
             'UserConfirmedBoardPowered':True,'UserNotifiedBeforeExecution':True,'Logs':{}}
    for name in ('scan.out.log','program.out.log'):
        path=directory/name;path.write_bytes(b'finite log identity fragment')
        program['Logs'][name]=a.sha(path)
    for name,lines in a.expected_program_scripts(selected).items():
        path=directory/(name+'.tcl');path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        plan['Tcl'][name]=a.reference(path)
    watched={}
    def bound(ref,*ignored):
        path=Path(ref['Path']);digest=a.sha(path)
        a.require(digest==ref['SHA256'],'log/script source SHA drift')
        watched[str(path)]=digest;return path
    return plan,program,work,selected,bound,watched


def test_both_required_program_logs_are_rehashed_and_bound(tmp_path):
    plan,program,work,selected,bound,watched=program_fragment(tmp_path)
    a.check_program_identity(plan,program,work,selected,'a'*64,bound)
    assert {str(work/'program-v3-a'/name) for name in ('scan.out.log','program.out.log')} <= set(watched)


@pytest.mark.parametrize('mutation',['missing_map','empty','scan_missing','program_missing','scan_badsha','program_badsha','boolsha','scan_drift','program_drift'])
def test_missing_or_misbound_actual_scan_program_logs_are_rejected(mutation,tmp_path):
    plan,program,work,selected,bound,watched=program_fragment(tmp_path)
    if mutation=='missing_map':program.pop('Logs')
    elif mutation=='empty':program['Logs']={}
    elif mutation=='scan_missing':program['Logs'].pop('scan.out.log')
    elif mutation=='program_missing':program['Logs'].pop('program.out.log')
    elif mutation=='scan_badsha':program['Logs']['scan.out.log']='bad sha'
    elif mutation=='program_badsha':program['Logs']['program.out.log']='F'*64
    elif mutation=='boolsha':program['Logs']['scan.out.log']=True
    elif mutation=='scan_drift':(work/'program-v3-a/scan.out.log').write_bytes(b'changed bytes')
    else:(work/'program-v3-a/program.out.log').write_bytes(b'changed bytes')
    with pytest.raises(ValueError):a.check_program_identity(plan,program,work,selected,'a'*64,bound)
