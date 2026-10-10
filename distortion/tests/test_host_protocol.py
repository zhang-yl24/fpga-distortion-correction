import binascii,json,math
from pathlib import Path
import unittest
from model.host_protocol import angle_phase,command_packet,telemetry_fields,require_ready,acknowledged
root=Path(__file__).resolve().parents[1]
class HostProtocolTests(unittest.TestCase):
    def ready(self):
        return dict(HV=1,CAM=0x5640,E=0,I=1,H=1,D=1,V=1,X=0,UF=0,MF=0,OW=0,TV=1,TF=0,HQ=5,HR=0,HC=8,HX=0,HD=0,HE=0,RA=0,AU=0,CF=20,TR=2581<<4,TA=0,AL=0x80)
    def test_packets_match_independent_rtl_fixtures(self):
        ref=json.loads((root/'build/host_control_sim/reference.json').read_text())
        packets=(root/'build/host_control_sim/packets.mem').read_text().splitlines()
        for i,angle in enumerate(ref['angles']):
            self.assertEqual(angle_phase(angle),ref['phases'][i])
            self.assertEqual(command_packet(1,i+1,angle_phase(angle)).hex(),packets[i])
    def test_modulo_and_nonfinite(self):
        self.assertEqual(angle_phase(-90),0xc0000000);self.assertEqual(angle_phase(720),0)
        for a in (math.inf,-math.inf,math.nan):
            with self.assertRaises(ValueError):angle_phase(a)
    def test_invalid_ranges(self):
        for args in ((3,0,0),(1,-1,0),(1,65536,0),(1,1,-1),(1,1,1<<32),(2,1,2)):
            with self.assertRaises(ValueError):command_packet(*args)
    def test_duplicate_fields(self):
        with self.assertRaises(ValueError):telemetry_fields('CAM=5640 HV=01 HV=01')
    def test_requires_live_supported_healthy_firmware(self):
        self.assertGreater(require_ready(self.ready()),40)
        for key,value in [('HV',0),('I',0),('UF',1),('TV',0),('TA',54000000),('AL',0xa0),('TR',3000<<4)]:
            f=self.ready();f[key]=value
            with self.assertRaises(ValueError):require_ready(f)
    def test_no_stale_or_controller_only_ack(self):
        before=self.ready();a=angle_phase(13.7);f={**before,'HQ':6,'HC':9,'HR':a,'RA':a}
        self.assertFalse(acknowledged(f,before,1,6,a))
        f['CF']=21;self.assertTrue(acknowledged(f,before,1,6,a))
        f['RA']=0;self.assertFalse(acknowledged(f,before,1,6,a))
    def test_count_wrap_and_uart_fault(self):
        before=self.ready();before['HC']=0xffffffff;f={**before,'HQ':6,'HC':0,'AU':1}
        self.assertTrue(acknowledged(f,before,2,6,1))
        f['HX']=1
        with self.assertRaises(ValueError):acknowledged(f,before,2,6,1)
if __name__=='__main__':unittest.main()
