"""Hardware guard must reject changed ISP tables, source closure and simulation evidence."""
from pathlib import Path
import contextlib,importlib.util,io,json,shutil,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('color_guard',ROOT/'tools/validate-camera-color-candidate.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)

class GuardTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'build/color_guard_tests';base.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base)
        self.root=Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(base.resolve()))
        files=['board/gamma_capture.v','board/gamma_capture.fdc','board/gamma_capture-pins.json',
            'board/gamma_capture-sources.json','board/ov5640_cadence_trial_commands.vh',
            'board/ov5640_colorbars_commands.vh','rtl/experimental/ov5640_cadence_trial_init.v']
        for target in ('gamma_capture_settled','gamma_capture_colorbars'):
            files.extend(f'board/{target}{suffix}' for suffix in ('.v','.fdc','-pins.json','-sources.json'))
        proof=json.loads((ROOT/'build/camera_colorbars_sim/source-sha256.json').read_text(encoding='utf-8-sig'))
        files+=list(proof)+['build/camera_colorbars_sim/source-sha256.json','build/camera_colorbars_sim/simulation.log']
        for name in set(files):
            dest=self.root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        self.original=guard.ROOT;guard.ROOT=self.root
    def tearDown(self):
        guard.ROOT=self.original
        self.assertTrue(self.root.is_relative_to((ROOT/'build/color_guard_tests').resolve()))
        self.temp.cleanup()
    def check(self,target):
        with contextlib.redirect_stdout(io.StringIO()):guard.validate(target)
    def mutate(self,name,a,b):
        path=self.root/name;original=path.read_text();self.assertIn(a,original);path.write_text(original.replace(a,b))
    def test_settled_accepted(self):self.check('gamma_capture_settled')
    def test_bars_accepted(self):self.check('gamma_capture_colorbars')
    def test_delay_changed(self):
        self.mutate('board/gamma_capture_settled.v','DELAY_MS(8000)','DELAY_MS(1)')
        with self.assertRaises(ValueError):self.check('gamma_capture_settled')
    def test_pin_changed(self):
        with (self.root/'board/gamma_capture_settled.fdc').open('a') as p:p.write('\n# changed')
        with self.assertRaises(ValueError):self.check('gamma_capture_settled')
    def test_manifest_dropped(self):
        path=self.root/'board/gamma_capture_settled-sources.json';items=json.loads(path.read_text());items.pop(4);path.write_text(json.dumps(items))
        with self.assertRaises(ValueError):self.check('gamma_capture_settled')
    def test_pattern_changed(self):
        self.mutate('board/ov5640_colorbars_commands.vh','503d8000','503d0000')
        with self.assertRaises(ValueError):self.check('gamma_capture_colorbars')
    def test_readback_check_removed(self):
        self.mutate('rtl/experimental/ov5640_colorbars_init.v',",16'h503d:checkable_write=1;",':checkable_write=1;')
        with self.assertRaises(ValueError):self.check('gamma_capture_colorbars')
    def test_simulation_failure(self):
        with (self.root/'build/camera_colorbars_sim/simulation.log').open('a') as p:p.write('\nFatal: changed evidence')
        with self.assertRaises(ValueError):self.check('gamma_capture_colorbars')

if __name__=='__main__':unittest.main()
