"""The bounded deadline includes full native STA plus the uncached CPU gate."""
import inspect
from pathlib import Path
import sys
from unittest import mock
import pytest
sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_tile8df8v3_bitstream as bit


@pytest.fixture
def context(tmp_path,monkeypatch):
    request=tmp_path/'request.json';request.write_text('{}')
    plan=tmp_path/'plan.json';plan.write_text('{}')
    adf=tmp_path/'final.adf';adf.write_text('unchanged verified ADF fixture')
    value={'Request':{kind:{'Path':str(tmp_path/kind),'SHA256':'a'*64}
                       for kind in (*bit.SIMULATIONS,'PhysicalProof','Profile')},
        'Simulations':{kind:{'Limits':'bounded actual RTL fixture'}for kind in bit.SIMULATIONS},
        'BuildPlan':plan,'Build':{'Command':['unexecuted-pds-shell']},'FinalADF':adf,
        'FinalADFSHA256':bit.sha(adf),'Watched':{},'Profile':{'Bound':True}}
    binder=mock.Mock(return_value=value)
    monkeypatch.setattr(bit,'audit_request',binder)
    monkeypatch.setattr(bit,'ROOT',tmp_path/'distortion')
    monkeypatch.setattr(bit.build,'work_path',lambda p:Path(p).resolve())
    monkeypatch.setattr(bit,'render',lambda *args:'unchanged runtime Tcl fixture\n')
    return request,tmp_path/'bit-fresh',binder


@pytest.mark.parametrize('maximum',[60,900,901,3600])
def test_long_uncached_gate_budget_is_explicit_and_saved_without_weakening_authority(context,maximum):
    request,work,binder=context
    plan,_,_=bit.recipe(request,work,maximum)
    assert plan['MaximumSeconds']==maximum
    binder.assert_called_once_with(request,use_cache=True)


@pytest.mark.parametrize('maximum',[59,3601,0,-1,3600.0,True,None])
def test_out_of_bounds_or_noninteger_wall_clock_budget_is_rejected_before_authority(context,maximum):
    request,work,binder=context
    with pytest.raises(ValueError,match='60..3600'):bit.recipe(request,work,maximum)
    binder.assert_not_called()


def test_default_is_3600_and_explicit_fresh_authority_still_bypasses_cache(context):
    request,work,binder=context
    plan,_,_=bit.recipe(request,work,fresh_authority=True)
    assert plan['MaximumSeconds']==3600
    assert inspect.signature(bit.prepare).parameters['maximum'].default==3600
    binder.assert_called_once_with(request,use_cache=False)


def test_runtime_gate_and_sta_execution_functions_are_byte_identical_to_prior_authorized_source():
    import ast
    old=bit.ROOT/'tools/hdmi_camera_fisheye_bitstream_c.py'
    def functions(path):
        source=path.read_text(encoding='utf-8-sig');tree=ast.parse(source)
        return {n.name:ast.get_source_segment(source,n)for n in tree.body if isinstance(n,ast.FunctionDef)}
    previous,current=functions(old),functions(bit.SELF)
    assert set(current)==set(previous)|{'directfill_frame_counts','bind_sustained'}
    assert current['audit_request'].count('    sustained=bind_sustained(plan,watched)\n')==1
    assert current['audit_request'].count(",'SustainedSimulation':sustained")==1
    current['audit_request']=current['audit_request'].replace('    sustained=bind_sustained(plan,watched)\n','',1).replace(",'SustainedSimulation':sustained",'',1)
    for name in previous.keys()-{'add','drift','physical_provider','bind_simulation','verify'}:
        assert previous[name]==current[name],name
    assert 'fresh_authority=True'in current['gate']
    assert 'use_cache=not fresh_authority'in current['recipe']
    assert 'time.monotonic() - start'in current['execute']
