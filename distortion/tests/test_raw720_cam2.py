"""Focused fixed720 parser, finite transaction and default-plan tests; no hardware."""
from pathlib import Path
import json, struct, sys, zlib
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_raw720_cam2 as b
import raw720_cam2_session as s
import guarded_protocol as gp
from frame_protocol import encode

def test_actual_candidate_clone_and_cdc():
    p=b.verify_sources();assert len(p['source_files'])==109
    pins=b.load(b.ROOT/b.OWN[2]);assert len(pins)==129 and pins['cam_data[5]']=='AA23' and pins['uart_rxd']=='B24'
    fdc=(b.ROOT/b.OWN[1]).read_text()
    assert '-group [get_clocks {clk_27m pixel_clk}]' not in fdc
    assert '-from [get_clocks camera_pclk] -to [get_clocks clk_27m] 8.0' in fdc
    tcl=(b.ROOT/b.OWN[3]).read_text();assert tcl.index('if {$summaries != 1 || $passes != 1}')<tcl.index('gen_bit_stream')
    assert b.MODE_CONTRACT['frame_end_units4']*4==1843200 and b.MODE_CONTRACT['bank_reserved_bytes']>=1843200

def test_reference_drift_rejected(monkeypatch):
    original=b.sha
    monkeypatch.setattr(b,'sha',lambda p:'0'*64 if Path(p)==b.ROOT/'rtl/experimental/dvp_mode_admission_monitor.v' else original(p))
    with pytest.raises(ValueError,match='frozen reference'):b.verify_sources()

def status(seq,*,session=0,cmdseq=0,op=0,accepted=0,complete=0,crc=0,flight=False):
    values={n:0 for n,_,_ in gp.STATUS_FIELDS}
    flags=(1<<0)|(1<<1)|(1<<2)|(1<<3)|(1<<10)|((1<<5)|(1<<6) if flight else 1<<15)
    values.update(uptime_ms=seq*1000,snapshot_seq=seq,session_id=session,last_received_seq=cmdseq,last_accepted_seq=cmdseq,last_opcode=op,last_result=1 if op else 0,
        flag_bits=flags,accepted_commands=accepted,admitted_frames=1 if complete else 0,completed_frames=complete,
        held_frame_id=complete,source_crc32=crc,written_beats=57600 if complete else 0,
        temperature_raw=2518<<4,temperature_code=2518,temperature_age_27mhz=3,temperature_samples=12,temperature_conversions=14,sensor_id=0x5640,safety_snapshot_age_core=3,stop_reason=1 if complete else 0)
    data=bytearray(128);data[:8]=b'PGSTAT02';struct.pack_into('<HHI',data,8,128,2,b.BUILD_TAG)
    for n,off,fmt in gp.STATUS_FIELDS:struct.pack_into('<'+fmt,data,off,values[n])
    struct.pack_into('<I',data,120,zlib.crc32(data[:120]));data[124:]=b'ST02';return bytes(data)

def test_new_tag_does_not_relax_old_codec():
    packet=status(1);assert s.decode_status(packet)['snapshot_seq']==1
    with pytest.raises(ValueError):gp.decode_status(packet,expected_build_tag=b.BUILD_TAG)
    other=bytearray(packet);struct.pack_into('<I',other,12,gp.BUILD_TAG);struct.pack_into('<I',other,120,zlib.crc32(other[:120]))
    with pytest.raises(ValueError):s.decode_status(other)

def test_status_crc_and_fixed_vga_size_rejected():
    bad=bytearray(status(1));bad[76]^=1
    with pytest.raises(ValueError):s.Stream().feed(bad)
    with pytest.raises(ValueError,match='header/size'):s.Stream().feed(encode(640,480,1,bytes(614400)))

def test_payload_magic_is_not_packet_boundary():
    payload=(b'PGSTAT02PGFRAME1'+bytes(1843200))[:1843200]
    wire=status(1)+encode(1280,720,1,payload)+status(2)
    parser=s.Stream();events=[]
    for start in range(0,len(wire),7919):events+=parser.feed(wire[start:start+7919])
    assert [k for k,_ in events]==['status','frame','status'] and events[1][1].payload==payload and not parser.buffer

@pytest.fixture
def planned(tmp_path,monkeypatch):
    monkeypatch.setattr(s,'APPROVED',tmp_path)
    builddir=tmp_path/'b';builddir.mkdir();bit=builddir/(b.TARGET+'.sbit');bit.write_bytes(b'fake')
    timing=builddir/'final.rtr';timing.write_text('All Constraints Met.')
    manifest={'Bitstream':str(bit),'TimingReport':str(timing)};b.write_new(builddir/'validated-build.json',manifest)
    monkeypatch.setattr(b,'validate_target',lambda _:manifest)
    monkeypatch.setattr(s,'_validated_build',lambda _:manifest)
    monkeypatch.setattr(s.capture,'validate_live_binding',lambda *a,**k:{'raw_capture_contract':b.RAW_CONTRACT,'source_count':109})
    monkeypatch.setattr(s.hw,'resolve_pds_bin',lambda p=None:tmp_path)
    monkeypatch.setattr(s.idle,'validate_heartbeat',lambda:{'bitstream_path':str(bit)})
    def prepare_idle(base,**kwargs):
        work=Path(base)/'idle';work.mkdir();p={'target':'heartbeat','operation':'volatile_sram_only','workdir':str(work),'pds_bin':str(tmp_path),'frequency':kwargs['frequency'],'validation':{'bitstream_path':str(bit)},'tcl':{}}
        for stage,text in s.hw._scripts(p['validation'],p['frequency']).items():
            path=work/(stage+'.tcl');path.write_text(text);p['tcl'][stage]={'path':str(path),'sha256':s.sha(path)}
        b.write_new(work/'plan.json',p);return p
    monkeypatch.setattr(s.idle,'prepare_plan',prepare_idle)
    monkeypatch.setattr(s.hw,'_start_owned',lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected device access')))
    review=tmp_path/'identity.json';b.write_new(review,{'schema':1,'camera_id':'replacement','lens_id':'new-lens','eye':'CAM2','profile_id':'old-vga','capture_mode_id':'old-vga','image_size':[640,480],'pixel_format':'RGB565_LE','connection_review':{k:True for k in s.capture.CONNECTION_FIELDS[:-1]}})
    return s.prepare_plan(review,builddir,tmp_path,port='COM5')

def test_plan_is_default_no_hardware_and_separate_mode(planned):
    _,binding,_=s.verify_plan(planned)
    assert planned['hardware_accessed'] is False and planned['frames']==1 and planned['lease_ms']==24000
    assert binding['image_size']==[1280,720] and binding['intrinsics'] is None and binding['profile_id']!='old-vga'
    assert not binding['connection_review']['programmed_bound_bitstream']

def test_uart_bound_rejects_bad_arguments(tmp_path):
    for seconds in [True,0,30,46,float('nan')]:
        with pytest.raises(ValueError):s.prepare_plan('unused','unused',tmp_path,port='COM5',seconds=seconds)

def test_changed_plan_rejected(planned):
    modified={**planned,'frames':2}
    with pytest.raises(ValueError,match='sealed'):s.verify_plan(modified)

def test_relative_build_path_normalized(planned):
    import os
    work=Path(planned['build_dir']);manifest=b.load(work/'validated-build.json')
    review=b.load(planned['binding_path'])['review_source']['path']
    binding=s._derive_binding(review,manifest,os.path.relpath(work,Path.cwd()))
    assert binding['build_binding']['validated_build']['path']==str(work/'validated-build.json')

def test_unfinished_post_validation_receipt_rejected(monkeypatch):
    work=b.APPROVED/'raw720-cam2-build-20261026-a'
    if not (work/'post-validation-receipt.json').is_file():pytest.skip('local actual finalized720 artifact absent')
    original=s.load
    def missing(path):
        if Path(path)==work/'post-validation-receipt.json':raise FileNotFoundError('simulated missing final receipt')
        return original(path)
    monkeypatch.setattr(s,'load',missing)
    with pytest.raises(FileNotFoundError):s._validated_build(work)

def test_post_receipt_cannot_bind_another_manifest(monkeypatch):
    work=b.APPROVED/'raw720-cam2-build-20261026-a'
    if not (work/'post-validation-receipt.json').is_file():pytest.skip('local actual finalized720 artifact absent')
    original=s.load
    def wrong(path):
        result=original(path)
        return {**result,'ValidatedBuildSHA256':'0'*64} if Path(path)==work/'post-validation-receipt.json' else result
    monkeypatch.setattr(s,'load',wrong)
    with pytest.raises(ValueError,match='receipt/manifest/hash'):s._validated_build(work)

@pytest.mark.parametrize('stage',['open','reset_input_buffer'])
def test_partial_serial_open_is_closed(monkeypatch,stage):
    import types
    events=[]
    class Partial:
        def open(self):
            events.append('open')
            if stage=='open':raise OSError('partial open')
        def reset_input_buffer(self):events.append('reset');raise KeyboardInterrupt('reset interrupted')
        def close(self):events.append('close')
    monkeypatch.setitem(sys.modules,'serial',types.SimpleNamespace(Serial=lambda **kwargs:Partial()))
    with pytest.raises((OSError,KeyboardInterrupt)):s._serial('COM5')
    assert events[-1]=='close' and events.count('close')==1

@pytest.mark.parametrize('receipt',[[],{'bad':'shape'}])
def test_unknown_program_state_restores_fixed_idle(planned,monkeypatch,receipt):
    events=[]
    def broken(plan):
        b.write_new(Path(plan['program_plan']['workdir'])/'receipt.json',receipt);raise RuntimeError('unknown mock programmer')
    monkeypatch.setattr(s,'execute_program',broken)
    monkeypatch.setattr(s.idle,'execute_plan',lambda operation,**k: events.append('idle') or mock_receipt(operation,'heartbeat',s.idle.GOLDEN_BIT_SHA256))
    result=s.execute_plan(planned)
    assert result['programming_state_unknown'] and events==['idle'] and not result['passed']

def test_scan_failure_without_program_attempt_skips_idle(planned,monkeypatch):
    receipt={'passed':False,'programming_attempted':False,'done_confirmed':False}
    def failed(plan):b.write_new(Path(plan['program_plan']['workdir'])/'receipt.json',receipt);return receipt
    monkeypatch.setattr(s,'execute_program',failed)
    monkeypatch.setattr(s.idle,'execute_plan',lambda *a,**k: (_ for _ in ()).throw(AssertionError('scan did not modify SRAM')))
    result=s.execute_plan(planned);assert not result['passed'] and 'idle_program' not in result

def test_capture_error_closes_com_before_idle(planned,monkeypatch):
    events=[]
    class Link:
        def write(self,data):events.append('stop');return len(data)
        def close(self):events.append('close')
    def programmed(plan):
        return mock_receipt(plan['program_plan'],s.TARGET,s.sha(plan['program_plan']['validation']['bitstream_path']))
    monkeypatch.setattr(s,'execute_program',programmed);monkeypatch.setattr(s,'_serial',lambda _:Link())
    monkeypatch.setattr(s,'run_uart',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('synthetic UART failure')))
    monkeypatch.setattr(s.idle,'execute_plan',lambda operation,**k: events.append('idle') or mock_receipt(operation,'heartbeat',s.idle.GOLDEN_BIT_SHA256))
    result=s.execute_plan(planned);assert not result['passed'] and result['com_closed'] and events==['stop','close','idle']

def mock_receipt(operation,target,digest):
    result={'target':target,'operation':'volatile_sram_only','workdir':operation['workdir'],'passed':True,
            'programming_attempted':True,'hardware_accessed':True,'done_confirmed':True,'bitstream_sha256':digest}
    b.write_new(Path(operation['workdir'])/'receipt.json',result);return result

def test_single_grant_full720_ack_completion_stop(planned):
    payload=(b'PGSTAT02PGFRAME1'+bytes(1843200))[:1843200];crc=zlib.crc32(payload);session=planned['host_session']
    class Link:
        def __init__(self):self.queue=[status(1),status(2)];self.sequence=2;self.commands=[]
        def write(self,data):
            cmd=gp.decode_command(data);self.commands.append(cmd);self.sequence+=1;seq=cmd['seq'];op=cmd['opcode']
            self.queue.append(status(self.sequence,session=session,cmdseq=seq,op=op,accepted=seq,complete=1 if seq==4 else 0,crc=crc if seq==4 else 0,flight=seq==3))
            if seq==3:
                assert cmd['requested_frames']==1 and cmd['lease_ms']==24000
                self.queue += [encode(1280,720,1,payload),status(self.sequence+1,session=session,cmdseq=3,op=16,accepted=3,complete=1,crc=crc)];self.sequence+=1
            return len(data)
        def read(self,_):return self.queue.pop(0) if self.queue else b''
    class Clock:
        def __init__(self):self.value=0
        def __call__(self):self.value+=.3;return self.value
    binding=b.load(planned['binding_path']);record={'raw_capture_contract':b.RAW_CONTRACT}
    link=Link();result=s.run_uart(link,planned,binding,record,clock=Clock())
    assert result['passed'] and len(result['frames'])==1 and [c['opcode'] for c in link.commands]==[15,18,16,17]
    frame=result['frames'][0];assert frame['payload_bytes']==1843200 and frame['input_mode_contract']==b.MODE_CONTRACT and frame['calibration_accepted'] is False

def test_zero_session_cannot_ack_open(planned):
    class Link:
        def __init__(self):self.queue=[status(1),status(2)]
        def write(self,data):
            cmd=gp.decode_command(data);assert cmd['opcode']==15
            self.queue.append(status(3,session=0,cmdseq=1,op=15,accepted=1));return len(data)
        def read(self,_):return self.queue.pop(0) if self.queue else b''
    tick=[0.]
    def clock():tick[0]+=.3;return tick[0]
    with pytest.raises(RuntimeError,match='session'):
        s.run_uart(Link(),planned,b.load(planned['binding_path']),{},clock=clock)
