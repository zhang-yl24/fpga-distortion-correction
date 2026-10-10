"""Fault-path checks use simulated UART; no hardware or subprocess is accessed."""
import contextlib,io,json,runpy,sys,types,unittest
from unittest.mock import patch
from pathlib import Path
from tests import test_host_protocol as fixtures
from model.host_protocol import angle_phase
root=Path(__file__).resolve().parents[1]
class FakeSerial:
    def __init__(self,lines,partial=False):self.lines=iter(lines);self.partial=partial;self.writes=[];self.closed=False
    def open(self):pass
    def readline(self):return next(self.lines,b'')
    def write(self,packet):self.writes.append(packet);return len(packet)-1 if self.partial else len(packet)
    def flush(self):pass
    def close(self):self.closed=True
class HostCliFaultTests(unittest.TestCase):
    def line(self,fields):return ('CAM=5640 '+' '.join(f'{k}={v:X}' for k,v in fields.items() if k!='CAM')+'\n').encode()
    def run_client(self,device,arguments=None):
        clock=iter(range(100));stdout=io.StringIO()
        with patch.dict(sys.modules,{'serial':types.SimpleNamespace(Serial=lambda *a,**k:device)}),patch.object(sys,'argv',['host-angle.py']+(arguments or ['--angle','13.7','--sequence','6','--execute'])),patch('subprocess.run',return_value=types.SimpleNamespace(returncode=0,stdout='mocked heartbeat only',stderr='')) as idle,patch('time.monotonic',side_effect=lambda:next(clock)),contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as end:runpy.run_path(str(root/'tools/host-angle.py'),run_name='__main__')
        self.assertTrue(device.closed);self.assertEqual(idle.call_count,1)
        return end.exception.code,json.loads(stdout.getvalue().splitlines()[-1])
    def test_unknown_firmware_sends_nothing_and_idles(self):
        f=fixtures.HostProtocolTests().ready();f['HV']=0;device=FakeSerial([self.line(f)])
        code,result=self.run_client(device);self.assertEqual(code,1);self.assertEqual(device.writes,[])
        self.assertIn('no command sent',result['error'])
    def test_partial_write_is_never_retried_and_idles(self):
        device=FakeSerial([self.line(fixtures.HostProtocolTests().ready())],partial=True)
        code,result=self.run_client(device);self.assertEqual(code,1);self.assertEqual(len(device.writes),1)
        self.assertIn('Partial UART write',result['error'])
    def test_success_requires_new_frame_and_idles(self):
        before=fixtures.HostProtocolTests().ready();phase=angle_phase(13.7)
        controller={**before,'HQ':6,'HC':9,'HR':phase,'RA':phase}
        displayed={**controller,'CF':21}
        device=FakeSerial([self.line(before),self.line(controller),self.line(displayed)])
        code,result=self.run_client(device);self.assertEqual(code,0);self.assertTrue(result['acknowledged'])
        self.assertEqual(result['after']['CF'],21);self.assertEqual(len(device.writes),1)
    def test_auto_mode_change_during_monitor_fails_and_idles(self):
        before=fixtures.HostProtocolTests().ready();accepted={**before,'HQ':6,'HC':9,'AU':1}
        changed={**accepted,'AU':0,'CF':21}
        device=FakeSerial([self.line(before),self.line(accepted),self.line(changed)])
        code,result=self.run_client(device,['--auto','1','--sequence','6','--execute','--observe-seconds','40'])
        self.assertEqual(code,1);self.assertIn('automatic mode changed',result['error']);self.assertEqual(len(device.writes),1)
    def test_uart_fault_after_ack_fails_and_idles(self):
        before=fixtures.HostProtocolTests().ready();phase=angle_phase(13.7)
        accepted={**before,'HQ':6,'HC':9,'HR':phase,'RA':phase,'CF':21}
        corrupt={**accepted,'HE':1,'CF':22}
        device=FakeSerial([self.line(before),self.line(accepted),self.line(corrupt)])
        code,result=self.run_client(device,['--angle','13.7','--sequence','6','--execute','--observe-seconds','40'])
        self.assertEqual(code,1);self.assertIn('UART counter fault',result['error']);self.assertEqual(len(device.writes),1)
if __name__=='__main__':unittest.main()
