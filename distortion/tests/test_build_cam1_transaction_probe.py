"""Fixed local source/build gates; no PDS/device access."""
from pathlib import Path
import copy
import sys

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_cam1_transaction_probe as b


def test_fixed_source8_electrical6_and_diagnostic_only_contract():
    p=b.verify_sources()
    assert len(p['SourceSHA256'])==8 and p['source_files']==b.SOURCE_FILES
    assert len(b.PIN_MAP)==len(set(b.PIN_MAP.values()))==6
    assert b.PIN_MAP['cam_rst_n']=='T20' and b.PIN_MAP['cam_sda']=='U14' and b.PIN_MAP['led0']=='A20'
    assert p['DiagnosticContract']==b.DIAGNOSTIC_CONTRACT
    assert not any(p['DiagnosticContract'][k] for k in ('raw_frames','ddr_outputs','hdmi_outputs'))


def simulated_header():
    return {'Passed':True,'HardwareAccessed':False,'Target':b.TARGET,
        'Cases':['complete_original_success','write4_read1_pending61'],
        'PreparedSourceManifestSHA256':b.sha(b.ROOT/f'board/{b.TARGET}-sources.json'),
        'SourceSHA256':{},'SourceSHA256After':{},'LogSHA256':{}}


@pytest.mark.parametrize('mode',['empty','missing-top','missing-uart'])
def test_simulation_cannot_omit_real_compiled_sources(mode,monkeypatch):
    m=simulated_header()
    if mode!='empty':
        m['SourceSHA256']={n:b.sha(b.ROOT/n) for n in b.SIM_SOURCE_FILES}
        del m['SourceSHA256'][f'board/{b.TARGET}.v' if mode=='missing-top' else 'rtl/uart_tx.v']
    m['SourceSHA256After']=copy.deepcopy(m['SourceSHA256'])
    monkeypatch.setattr(b,'load',lambda path:m)
    with pytest.raises(ValueError,match='source13'):b.verify_simulation(b.APPROVED/'pretend.json')


def test_simulation_cannot_omit_compile_elab_uart_logs(monkeypatch):
    m=simulated_header();m['SourceSHA256']={n:b.sha(b.ROOT/n) for n in b.SIM_SOURCE_FILES}
    m['SourceSHA256After']=copy.deepcopy(m['SourceSHA256'])
    monkeypatch.setattr(b,'load',lambda path:m)
    with pytest.raises(ValueError,match='logs required'):b.verify_simulation(b.APPROVED/'pretend.json')


@pytest.mark.parametrize('payload',[b'',b'PGCAMD01',bytes(64)])
def test_empty_partial_or_bad_crc_wire_is_rejected(payload,monkeypatch):
    monkeypatch.setattr(Path,'read_bytes',lambda path:payload)
    with pytest.raises(ValueError):b.audit_uart_wires(b.APPROVED)


def test_routed_inout_cannot_be_relabelled_output(monkeypatch):
    rows=[]
    for port,pad in b.PIN_MAP.items():
        direction='input' if port=='clk_27m' else 'inout' if port.startswith('cam_') else 'output'
        if port=='cam_sda':direction='output'
        rows.append('|'.join([pad,'IO','BANK','SITE',port,direction,'YES']))
    monkeypatch.setattr(Path,'read_text',lambda path,*args,**kwargs:'\n'.join(rows))
    with pytest.raises(ValueError,match='direction'):b.validate_pins(b.APPROVED/'pretend.prt')


def test_default_build_plan_never_invokes_pds(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'APPROVED',tmp_path)
    monkeypatch.setattr(b.subprocess,'Popen',lambda *a,**k:pytest.fail('default plan invoked PDS'))
    p=b.run_build(tmp_path/'plan')
    assert p['ExecuteBuild'] is False and p['HardwareAccessed'] is False and p['NoFlashOrProgrammingOperation'] is True
    assert not (tmp_path/'plan/validated-build.json').exists()


def test_actual_build_requires_uart_before_creating_output(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'APPROVED',tmp_path)
    with pytest.raises(ValueError,match='UART simulation required'):b.run_build(tmp_path/'missing',execute=True)
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('bound',[True,float('nan'),59,1801])
def test_build_bound_is_strict(bound):
    with pytest.raises(ValueError,match='bound'):b.run_build(b.APPROVED/'never-created',timeout_seconds=bound)
