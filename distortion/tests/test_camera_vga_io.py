"""CPU-only checks for camera-specific IO evidence; native fixtures are synthetic."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_io as io


class CameraIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=io.PROJECT
        cls.kw={key:(p/name).read_text(encoding='utf-8-sig') for key,name in {
            'top':'board/camera_vga_output_top.v','fdc':'board/camera-vga-output-diagnostic.fdc',
            'pcf':'work/camera-vga-output/pds-20261031-a/device_map/camera_vga_output_top.pcf',
            'prt':'work/camera-vga-output/pds-20261031-a/place_route/camera_vga_output_top_prr_route_optimize.prt',
            'exported':'work/camera-vga-output/export-final-20261031-a/generate_netlist/camera_vga_output_top_sim.v',
            'official':'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
            'cam_reference':'board/raw_camera_capture_cam2_ref.fdc'}.items()}
        cls.kw['cam_pins']=json.loads((p/'board/raw_camera_capture_cam2_ref-pins.json').read_text())
        cls.pins=io.pin_audit(**cls.kw)

    def fixture_log(self):
        lines=[]
        for row in self.pins['PinInventory']:
            names=sorted({c['NativeInstance'] for c in row['FinalPrimitiveConnections']})
            lines += [f"Site {row['Site']} ({len(names)}) :"]
            lines += ['\t'+name+' (synthetic instance fixture)' for name in names]
        return '\n'.join(lines)+'\nExecuting : show -dev_instance fixture successfully.\n'

    def test_all_current_ports_and_provisional_electrical_boundary(self):
        self.assertEqual(self.pins['TopPortCount'],128)
        self.assertEqual(self.pins['DDRMemoryPins'],71)
        self.assertEqual(self.pins['CAM2Pins'],14)
        self.assertFalse(self.pins['FinalNativeElectricalAttributesVerified'])
        self.assertTrue(self.pins['FunctionalLibraryParameterDifferences'])

    def test_site_parser_fixture_does_not_grant_electrical_acceptance(self):
        pins=deepcopy(self.pins)
        io.apply_native_sites(pins,self.fixture_log())
        self.assertTrue(pins['FinalNativeSiteMappingPassed'])
        self.assertFalse(pins['FinalNativeElectricalAttributesVerified'])

    def test_missing_native_site_rejected(self):
        log=self.fixture_log();begin=log.index('Site ');end=log.index('Site ',begin+5)
        with self.assertRaisesRegex(ValueError,'site coverage'):
            io.apply_native_sites(deepcopy(self.pins),log[:begin]+log[end:])

    def test_wrong_native_io_instance_rejected(self):
        row=self.pins['PinInventory'][0]
        name=row['FinalPrimitiveConnections'][0]['NativeInstance']
        with self.assertRaisesRegex(ValueError,'instance/site differs'):
            io.apply_native_sites(deepcopy(self.pins),self.fixture_log().replace(name,'wrong/native_instance',1))

    def test_extra_native_io_instance_rejected(self):
        row=self.pins['PinInventory'][0]
        count=len({c['NativeInstance'] for c in row['FinalPrimitiveConnections']})
        old=f"Site {row['Site']} ({count}) :\n"
        new=f"Site {row['Site']} ({count+1}) :\n\textra/native_instance (synthetic extra)\n"
        with self.assertRaisesRegex(ValueError,'instance/site differs'):
            io.apply_native_sites(deepcopy(self.pins),self.fixture_log().replace(old,new,1))

    def test_duplicate_native_site_rejected(self):
        log=self.fixture_log()
        with self.assertRaisesRegex(ValueError,'duplicate native site'):
            io.apply_native_sites(deepcopy(self.pins),log+log)

    def test_d5_reference_pad_mismatch_rejected(self):
        kw=dict(self.kw);kw['cam_pins']=dict(kw['cam_pins']);kw['cam_pins']['cam_data[5]']='AA24'
        with self.assertRaisesRegex(ValueError,'CAM2 reference'):
            io.pin_audit(**kw)

    def test_actual_pcf_drift_rejected(self):
        kw=dict(self.kw);kw['pcf']=kw['pcf'].replace('LOC=Y20','LOC=Y21',1)
        with self.assertRaisesRegex(ValueError,'PCF electrical attrs'):
            io.pin_audit(**kw)

    def test_final_scalar_attribute_drift_rejected(self):
        kw=dict(self.kw);kw['exported']=kw['exported'].replace('PAP_IO_LOC="W23"','PAP_IO_LOC="W24"',1)
        with self.assertRaisesRegex(ValueError,'scalar pad attrs differ'):
            io.pin_audit(**kw)


if __name__=='__main__':unittest.main()
