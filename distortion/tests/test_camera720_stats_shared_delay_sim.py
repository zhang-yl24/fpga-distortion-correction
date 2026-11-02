from pathlib import Path
import csv
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_camera720_stats_shared_delay_sim as sim

TOP="""module camera720_calibrated_stats_delay_top();
raw_camera_input_delay camera_data_delay(.pad_data(cam_data),.capture_data(delayed_cam_data));
raw_camera_control_input_delay camera_control_delay(.pad_href(cam_href),.pad_vsync(cam_vsync),.capture_href(delayed_cam_href),.capture_vsync(delayed_cam_vsync));
video system(.cam_clk(cam_pclk),.cam_data(delayed_cam_data),.cam_href(delayed_cam_href),.cam_vsync(delayed_cam_vsync));
frontend camera_configuration(.pclk(cam_pclk),.vsync_active(!delayed_cam_vsync),.href_active(!delayed_cam_href));
endmodule
"""


def observations(path):
    previous=0;rows=[]
    for index in range(1024):
        value=index^0x2a5
        rows.append({'index':str(index),'previous':f'{previous:03x}','driven':f'{value:03x}',
            'before1500ps':f'{previous:03x}','after1500ps':f'{value:03x}','stable':f'{value:03x}'})
        previous=value
    samples=[];offsets=[1,100,1000,1499,1501,2000,8000,15000]
    for index in range(32):
        value=previous^1023;offset=offsets[index%8]
        samples.append({'index':str(index),'offset_ps':str(offset),'previous':f'{previous:03x}','driven':f'{value:03x}',
            'sampled_capture':f'{previous if offset<1500 else value:03x}','sampled_delayed_monitor':f'{(previous if offset<1500 else value)>>8:x}'})
        previous=value
    for name,values in [('transitions.csv',rows),('sampling.csv',samples)]:
        with (path/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
    return rows,samples


class ControlDataDelaySimulationTests(unittest.TestCase):
    def test_complete_observation_fixture_has_all_lanes_polarities(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);observations(path);value=sim.inspect_observations(path)
            self.assertTrue(all(value['LaneRisingTransitions']))
            self.assertTrue(all(value['LaneFallingTransitions']))
            self.assertFalse(value['ExtraPixelClockCycleObserved'])

    def test_early_control_bypass_and_late_lane_are_rejected(self):
        for field,mutation in [('before1500ps',lambda r:r['driven']),('after1500ps',lambda r:r['previous']),
                               ('stable',lambda r:f"{int(r['driven'],16)^256:03x}")]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);rows,_=observations(path);rows[4][field]=mutation(rows[4])
                with (path/'transitions.csv').open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
                with self.assertRaises(ValueError):sim.inspect_observations(path)

    def test_extra_sample_cycle_and_delayed_monitor_rejected(self):
        for field in ('sampled_capture','sampled_delayed_monitor'):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);_,rows=observations(path);index=4 if field=='sampled_capture' else 0
                rows[index][field]=rows[index]['previous'] if field=='sampled_capture' else f"{int(rows[index]['driven'],16)>>8:x}"
                with (path/'sampling.csv').open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
                with self.assertRaises(ValueError):sim.inspect_observations(path)

    def test_missing_phase_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);observations(path)
            p=path/'sampling.csv';p.write_text('\n'.join(p.read_text().splitlines()[:-1])+'\n')
            with self.assertRaises(ValueError):sim.inspect_observations(path)

    def test_generated_top_raw_monitor_and_delayed_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'top.v';p.write_text(TOP)
            self.assertTrue(sim.top_wiring(p)['MonitorAfterControlDelay'])
            self.assertFalse(sim.top_wiring(p)['RawMonitorPathPreserved'])
            for old,new in [('.cam_href(delayed_cam_href)','.cam_href(cam_href)'),
                            ('.href_active(!delayed_cam_href)','.href_active(!cam_href)'),
                            ('.cam_clk(cam_pclk)','.cam_clk(delayed_clock)'),
                            ('.capture_href(delayed_cam_href)','.capture_href(delayed_cam_vsync)')]:
                p.write_text(TOP.replace(old,new))
                with self.subTest(old=old),self.assertRaises(ValueError):sim.top_wiring(p)

if __name__=='__main__':unittest.main()
