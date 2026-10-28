from pathlib import Path
import os,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pds_source_manifest import expand_sources


class SourceManifestTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(os.environ.get('FPGA_TEST_WORKDIR',str(Path(__file__).resolve().parents[1]/'build/source_manifest_tests'))).resolve()
        self.base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.base);self.root=Path(self.temp.name).resolve()
        assert self.root.is_relative_to(self.base)
        (self.root/'ip').mkdir();(self.root/'ip/core.vp').write_text('encrypted vendor source')
    def tearDown(self):
        assert self.root.resolve().is_relative_to(self.base)
        self.temp.cleanup()
    def idf(self,content):
        (self.root/'ip/core.idf').write_text(content)
    def test_vendor_source_included_and_sim_output_excluded(self):
        self.idf('<ip_inst><file_list><output><file pathname="nonexistent-sim.v"/></output><source><file pathname="core.vp"/></source></file_list></ip_inst>')
        self.assertEqual(expand_sources(self.root,['ip/core.idf']),['ip/core.idf','ip/core.vp'])
    def test_missing_vendor_source_is_failure(self):
        self.idf('<ip_inst><file_list><source><file pathname="missing.vp"/></source></file_list></ip_inst>')
        with self.assertRaises(ValueError):expand_sources(self.root,['ip/core.idf'])
    def test_escape_project_is_failure(self):
        self.idf('<ip_inst><file_list><source><file pathname="../../outside.vp"/></source></file_list></ip_inst>')
        with self.assertRaises(ValueError):expand_sources(self.root,['ip/core.idf'])
    def test_missing_source_list_is_failure(self):
        self.idf('<ip_inst><file_list/></ip_inst>')
        with self.assertRaises(ValueError):expand_sources(self.root,['ip/core.idf'])
    def test_duplicate_sources_not_hashed_twice(self):
        self.idf('<ip_inst><file_list><source><file pathname="core.vp"/><file pathname="core.vp"/></source></file_list></ip_inst>')
        self.assertEqual(expand_sources(self.root,['ip/core.idf','ip/core.vp']),['ip/core.idf','ip/core.vp'])


if __name__=='__main__':unittest.main()
