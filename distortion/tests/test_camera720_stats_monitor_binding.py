"""Fault injections at the release monitor evidence boundary; CPU only."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_bitstream as bit
import run_camera720_stats_shared_monitor_sim as monitor

TOP='''module camera720_calibrated_stats_delay_top();
raw_camera_input_delay camera_data_delay(.pad_data(cam_data),.capture_data(delayed_cam_data));
raw_camera_control_input_delay camera_control_delay(.pad_href(cam_href),.pad_vsync(cam_vsync),.capture_href(delayed_cam_href),.capture_vsync(delayed_cam_vsync));
video system(.cam_clk(cam_pclk),.cam_data(delayed_cam_data),.cam_href(delayed_cam_href),.cam_vsync(delayed_cam_vsync));
frontend camera_configuration(.pclk(cam_pclk),.vsync_active(!delayed_cam_vsync),.href_active(!delayed_cam_href));
endmodule
'''


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    project=tmp_path/'project';project.mkdir()
    monkeypatch.setattr(bit.prep,'PROJECT',project)
    def write(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value,dict) else value,encoding='utf-8')
        return path
    runner_path=write(project/'tools/run_camera720_stats_shared_monitor_sim.py','fixture runner identity')
    provider=SimpleNamespace(__file__=str(runner_path),CASES=monitor.CASES,SOURCES=monitor.SOURCES,
        HEADERS=monitor.HEADERS,observations=monitor.observations,delay=monitor.delay)
    monkeypatch.setattr(bit,'module',lambda name:provider)
    build=write(project/'build/plan.json',{})
    top=write(build.parent/'source'/bit.inspect.TOP,TOP)
    inputs={str(runner_path):bit.sha(runner_path),str(top):bit.sha(top)}
    for name in (*monitor.SOURCES[:-1],monitor.HEADERS[0]):
        path=write(project/name,'unchanged '+name);inputs[str(path)]=bit.sha(path)
        write(build.parent/'source'/name,path.read_text())
    report=project/'simulation/report.json'
    cases=[];evidence={}
    for name,half,bad,args in monitor.CASES:
        summary={'Passed':True,'PCLKHalfPeriodPS':half,'BadLineCase':int(bad),'Configured':1,
            'RawAuthorize':0,'GoodFrames':0 if bad else 2,'BadFrames':0,
            'LastLines':0 if bad else 720,'LastBytes':2560,'Fault':0x12 if bad else 0xc0}
        log=write(report.parent/(name+'.log'),monitor.BAD_MARKER if bad else '\n'.join(monitor.GOOD_MARKERS))
        data=write(report.parent/(name+'-summary.json'),summary)
        evidence.update({p.name:bit.sha(p) for p in (log,data)})
        cases.append({'Name':name,'Passed':True,'Summary':summary,'Log':log.name,'SummaryFile':data.name})
    value={'Schema':'camera720-stats-shared-control-monitor-simulation-v1','Target':bit.prep.TARGET,
        'Passed':True,'SimulationExecuted':True,'InputDrift':[],'Geometry':[2560,720],
        'PCLKModelHz':[42000000,47250000],'MonitorAfterControlDelay':True,
        'RawMonitorPathPreserved':False,'MonitorSamplePhaseShiftPS':1500,
        'InputSHA256':inputs,'EvidenceSHA256':evidence,'Cases':cases,
        'GeneratedTop':{'Path':str(top),'SHA256':bit.sha(top)},'TopWiring':monitor.delay.top_wiring(top)}
    def seal():
        write(report,value);monkeypatch.setattr(bit,'MONITOR_SIM_SHA',bit.sha(report))
        return report
    def bind():return bit.monitor_binding(seal(),build,{})
    return SimpleNamespace(value=value,path=report,build=build,top=top,write=write,seal=seal,bind=bind)


def test_complete_four_cases_replay_real_observation_validator(fixture):
    fixture.bind()


@pytest.mark.parametrize('mutation',['missing','duplicate','order','case_false','artifact_alias'])
def test_missing_or_mismatched_case_cannot_pass_even_with_resigned_fixture(fixture,mutation):
    v=fixture.value
    if mutation=='missing':v['Cases'].pop()
    if mutation=='duplicate':v['Cases'][-1]=deepcopy(v['Cases'][0])
    if mutation=='order':v['Cases'].reverse()
    if mutation=='case_false':v['Cases'][2]['Passed']=False
    if mutation=='artifact_alias':v['Cases'][3]['SummaryFile']=v['Cases'][2]['SummaryFile']
    with pytest.raises(ValueError):fixture.bind()


def test_omitted_bound_case_artifact_rejected(fixture):
    fixture.value['EvidenceSHA256'].pop(fixture.value['Cases'][3]['SummaryFile'])
    with pytest.raises(ValueError,match='evidence missing'):fixture.bind()


def test_artifact_drift_rejected_without_trusting_report_boolean(fixture):
    case=fixture.value['Cases'][0];path=fixture.path.parent/case['SummaryFile']
    fixture.write(path,{**case['Summary'],'GoodFrames':1})
    with pytest.raises(ValueError,match='SHA differs'):fixture.bind()


@pytest.mark.parametrize('index,field,bad',[(0,'GoodFrames',1),(1,'LastLines',719),
    (1,'Fault',0),(2,'GoodFrames',1),(3,'RawAuthorize',1)])
def test_consistent_bad_actual_case_is_rejected_by_replayed_validator(fixture,index,field,bad):
    case=fixture.value['Cases'][index];case['Summary'][field]=bad
    path=fixture.write(fixture.path.parent/case['SummaryFile'],case['Summary'])
    fixture.value['EvidenceSHA256'][path.name]=bit.sha(path)
    with pytest.raises(ValueError):fixture.bind()


def test_original_raw_monitor_wiring_rejected(fixture):
    fixture.write(fixture.top,TOP.replace('href_active(!delayed_cam_href)','href_active(!cam_href)'))
    fixture.value['InputSHA256'][str(fixture.top)]=bit.sha(fixture.top)
    fixture.value['GeneratedTop']['SHA256']=bit.sha(fixture.top)
    with pytest.raises(ValueError,match='monitor must share'):fixture.bind()


def test_generated_source_copy_cannot_drift_from_simulated_source(fixture):
    path=fixture.build.parent/'source'/monitor.SOURCES[0]
    fixture.write(path,'changed control delay')
    with pytest.raises(ValueError,match='SHA differs'):fixture.bind()


def test_exact_simulation_receipt_sha_is_required(fixture):
    fixture.seal();fixture.path.write_text(fixture.path.read_text()+' ')
    with pytest.raises(ValueError,match='exact completed'):bit.monitor_binding(fixture.path,fixture.build,{})
