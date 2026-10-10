"""Require both physical constraints and expected pin manifest to correct D5."""
from pathlib import Path
import importlib.util,json,tempfile,unittest,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('d5_guard',ROOT/'tools/prepare-d5-fixed-candidates.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
class D5Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'build')
        self.saved=guard.ROOT;guard.ROOT=Path(self.temp.name)
        (guard.ROOT/'board').mkdir()
        self.target='corrected_gamma_d5';self.old='corrected_gamma'
        b=guard.ROOT/'board'
        (b/f'{self.old}.v').write_text('module corrected_gamma(); endmodule\n')
        (b/f'{self.old}.fdc').write_text('define_attribute {p:cam_data[5]} {PAP_IO_LOC} {AA22}\ncreate_clock -period 8 test\n')
        (b/f'{self.old}-pins.json').write_text(json.dumps({'cam_data[5]':'AA22','cam_data[4]':'AB25'}))
        (b/f'{self.old}-sources.json').write_text(json.dumps([f'board/{self.old}.v',f'board/{self.old}.fdc',f'board/build-{self.old}.tcl']))
        (b/f'build-{self.old}.tcl').write_text('compile -top_module corrected_gamma\npnr -gplace_seed 2\n')
        names,top,fdc,pins,tcl=guard.expected(self.target)
        for suffix,txt in (('.v',top),('.fdc',fdc),('-pins.json',json.dumps(pins)),('-sources.json',json.dumps(names))):
            (b/f'{self.target}{suffix}').write_text(txt)
        (b/f'build-{self.target}.tcl').write_text(tcl)
    def tearDown(self):
        guard.ROOT=self.saved
        if not Path(self.temp.name).resolve().is_relative_to((ROOT/'build').resolve()):raise ValueError('Temporary cleanup escaped build workspace')
        self.temp.cleanup()
    def test_exact_fix_accepted(self):guard.validate(self.target)
    def test_wrong_manifest_rejected(self):
        p=guard.ROOT/f'board/{self.target}-pins.json';p.write_text(json.dumps({'cam_data[5]':'AA22','cam_data[4]':'AB25'}))
        with self.assertRaises(ValueError):guard.validate(self.target)
    def test_wrong_constraint_rejected(self):
        p=guard.ROOT/f'board/{self.target}.fdc';p.write_text(p.read_text().replace('AA23','AA22'))
        with self.assertRaises(ValueError):guard.validate(self.target)
    def test_clock_change_rejected(self):
        p=guard.ROOT/f'board/{self.target}.fdc';p.write_text(p.read_text().replace('-period 8','-period 16'))
        with self.assertRaises(ValueError):guard.validate(self.target)
    def test_pin_collision_rejected(self):
        p=guard.ROOT/f'board/{self.old}-pins.json';pins=json.loads(p.read_text());pins['cam_data[4]']='AA23';p.write_text(json.dumps(pins))
        with self.assertRaises(ValueError):guard.validate(self.target)
    def test_source_omission_rejected(self):
        p=guard.ROOT/f'board/{self.target}-sources.json';p.write_text('[]')
        with self.assertRaises(ValueError):guard.validate(self.target)
if __name__=='__main__':unittest.main()
