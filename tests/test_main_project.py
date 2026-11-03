import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fpga_project', ROOT / 'project.py')
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)


class MainProjectTests(unittest.TestCase):
    def test_unsafe_header_path_rejected_before_build(self):
        for name in ('bad"path', 'bad{path', 'bad}path', 'bad\npath', 'bad\tpath'):
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                project.safe_output(Path(tempfile.gettempdir()) / name)

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / 'source.v'
            sentinel.write_bytes(b'original FPGA source')
            with self.assertRaises(ValueError):
                project.safe_output(folder)
            self.assertEqual(sentinel.read_bytes(), b'original FPGA source')

    def test_new_short_build_directory_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'new build'
            self.assertEqual(project.safe_output(target), target.resolve())
            self.assertFalse(target.exists())

    def test_catalog_rejects_unmerged_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.git').mkdir()
            data = {'variants': [], 'releases': [], 'branches': [{'ref': 'test', 'commit': 'a' * 40}]}
            with patch.object(project, 'ROOT', root), patch.object(project, 'catalog', return_value=data), patch.object(project.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
                with self.assertRaisesRegex(ValueError, 'Unintegrated branch'):
                    project.audit()

    def test_release_asset_requires_sha256(self):
        data = {'variants': [], 'releases': [{'assets': [{'name': 'old.zip', 'digest': None}]}], 'branches': []}
        with patch.object(project, 'catalog', return_value=data):
            with self.assertRaisesRegex(ValueError, 'Invalid release digest'):
                project.audit()


if __name__ == '__main__':
    unittest.main()
