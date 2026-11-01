from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_raw_camera_delay_reset_effect import compare_file_tables


class FileTableTests(unittest.TestCase):
    def test_empty_filename_removal_is_metadata_only(self):
        r = compare_file_tables(['FILETABLE', ['FILEMAP', '2', '""']], ['FILETABLE'])
        self.assertEqual(r['RemovedEmptyIDs'], ['2'])

    def test_real_filename_removal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            compare_file_tables(['FILETABLE', ['FILEMAP', '2', '"source.v"']], ['FILETABLE'])

    def test_real_filename_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'added or changed'):
            compare_file_tables(['FILETABLE', ['FILEMAP', '2', '"a.v"']], ['FILETABLE', ['FILEMAP', '2', '"b.v"']])

    def test_new_mapping_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'added or changed'):
            compare_file_tables(['FILETABLE'], ['FILETABLE', ['FILEMAP', '2', '""']])

    def test_existing_real_mapping_is_preserved(self):
        table = ['FILETABLE', ['FILEMAP', '2', '"a.v"']]
        self.assertEqual(compare_file_tables(table, table)['RemovedEmptyIDs'], [])


if __name__ == '__main__': unittest.main()
