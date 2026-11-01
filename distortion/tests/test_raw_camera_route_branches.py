"""Branch-detour checks must reject collateral route or semantic changes."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_raw_camera_routes as audit


def node(pin, x, y, *children):
    return [['PORTREF', pin, ['DEVINSTREF', 'SRB', ['SITEREF', str(x), str(y)]]], *children]


class BranchTests(unittest.TestCase):
    def test_native_indexed_annotation_name(self):
        self.assertEqual(audit.annotation_name('( INDEXED nt_cam_data 2 )'), 'nt_cam_data[2]')

    def fixture(self):
        before = {'NonRouteSemanticSHA256': 'same', 'NetAnnotations': {'camera': 'old', 'other': 'other'},
                  'ExcludedBlockSHA256': {'FILETABLE': 'files', 'CDB': 'constraints'},
                  'BranchInventory': {'camera': {'LogicalConnections': ['source', 'a', 'b'],
                                                 'Leaves': {'a': ['source', 'a'], 'b': ['source', 'b']}}}}
        after = copy.deepcopy(before)
        after['NetAnnotations']['camera'] = 'new'
        after['BranchInventory']['camera']['Leaves']['a'] = ['source', 'detour', 'a']
        return before, after, [{'Net': 'camera', 'ToRoutePin': 'a'}]

    def test_multibranch_native_tree_keeps_separate_leaves(self):
        leaves = audit.route_leaves(['ROUTE', node('SOURCE', 1, 2, node('A', 3, 4), node('B', 5, 6))])
        self.assertEqual(leaves, {'A:SRB_3_4': ['SOURCE:SRB_1_2', 'A:SRB_3_4'],
                                  'B:SRB_5_6': ['SOURCE:SRB_1_2', 'B:SRB_5_6']})

    def test_one_branch_detour_is_allowed(self):
        self.assertTrue(audit.compare(*self.fixture())['Passed'])

    def test_sibling_route_change_is_rejected(self):
        before, after, targets = self.fixture()
        after['BranchInventory']['camera']['Leaves']['b'] = ['source', 'unexpected', 'b']
        with self.assertRaisesRegex(ValueError, 'sibling branch'):
            audit.compare(before, after, targets)

    def test_unrelated_net_change_is_rejected(self):
        before, after, targets = self.fixture()
        after['NetAnnotations']['other'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'unrequested net'):
            audit.compare(before, after, targets)

    def test_constraint_change_is_not_silently_accepted(self):
        before, after, targets = self.fixture()
        after['ExcludedBlockSHA256']['CDB'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'constraint database'):
            audit.compare(before, after, targets)

    def test_functional_change_rejected_even_with_reset_scope(self):
        before, after, targets = self.fixture()
        after['NonRouteSemanticSHA256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'semantics changed'):
            audit.compare(before, after, targets, allow_constraint_change=True)


if __name__ == '__main__':
    unittest.main()
