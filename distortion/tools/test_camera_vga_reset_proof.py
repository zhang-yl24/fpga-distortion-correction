"""CPU-only negative checks for exact pin evidence and actual camera reset graph."""
from copy import deepcopy
from pathlib import Path
import json
import re
import tempfile
import unittest

import audit_camera_vga_reset_netlist as graph
import audit_camera_vga_reset_proof as proof

BASE = Path(__file__).resolve().parents[1]
PLAN = BASE / 'results/camera-vga-reset-analysis-20261031-a/full-scope/plan.json'
NETLIST = BASE / 'work/camera-vga-output/export-baseline-20261031-a/generate_netlist/camera_vga_output_top_sim.v'


def change_port(text, cell, pin, old, new):
    anchor = '\\' + cell + '  ('
    if text.count(anchor) != 1:
        raise ValueError('cell mutation anchor is not unique')
    start = text.index(anchor)
    end = text.index(');', start) + 2
    body, count = re.subn(r'(\.' + pin + r'\s*\(\s*)' + re.escape(old) + r'(\s*\))',
                          lambda m: m[1] + new + m[2], text[start:end])
    if count != 1:
        raise ValueError('port mutation is not unique')
    return text[:start] + body + text[end:]


class CameraResetProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = json.loads(PLAN.read_text(encoding='utf-8'))['NativeQueries']
        cls.text = NETLIST.read_text(encoding='utf-8-sig')
        cls.actual = graph.audit_text(cls.text, cls.queries)

    def native_lines(self):
        rows = []
        for query in self.queries:
            for pattern, names in ((query['FromRegex'], [query['Source']]),
                                   (query['ToRegex'], query['Targets'])):
                rows.append("I: Timing-5001: The pattern '" + pattern +
                            "' in command 'get_pins -hierarchical -regexp {" + pattern +
                            "}' match " + str(len(names)) + ' objects below: ' +
                            ' '.join('t:' + name for name in names))
        return rows

    def match_lines(self, rows):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / 'test.log'
            log.write_text('\n'.join(rows) + '\n', encoding='utf-8')
            return proof.exact_queries(self.queries, log)

    def test_synthetic_exact_log_is_accepted_only_as_parser_fixture(self):
        self.assertEqual(len(self.match_lines(self.native_lines())), 2 * len(self.queries))

    def test_duplicate_native_record_rejected(self):
        rows = self.native_lines()
        with self.assertRaisesRegex(ValueError, 'missing or duplicated'):
            self.match_lines(rows + [rows[0]])

    def test_same_count_wrong_native_name_rejected(self):
        rows = self.native_lines()
        rows[0] = rows[0].rsplit('t:', 1)[0] + 't:wrong_cell/CLK'
        with self.assertRaisesRegex(ValueError, 'exact names/count differs'):
            self.match_lines(rows)

    def test_missing_native_record_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing or duplicated'):
            self.match_lines(self.native_lines()[:-1])

    def test_second_stage_bypass_rejected(self):
        stage = self.actual['Stages'][1]
        mutated = change_port(self.text, stage['Name'], 'D', stage['Ports']['D'], graph.syntax.LOCK)
        with self.assertRaises(ValueError):
            graph.audit_text(mutated, self.queries)

    def test_first_stage_extra_functional_fanout_rejected(self):
        power = self.actual['PowerReadyFF']
        mutated = change_port(self.text, power['Name'], 'D', power['Ports']['D'], self.actual['Stages'][0]['Ports']['Q'])
        with self.assertRaisesRegex(ValueError, 'first-stage functional fanout'):
            graph.audit_text(mutated, self.queries)

    def test_one_reset_target_rewired_rejected(self):
        dqs = next(g for g in self.actual['InternalDriverGroups'] if len(g['Targets']) > 1)
        target = dqs['Targets'][0]
        mutated = change_port(self.text, target['FunctionalCell'], target['Pin'], target['Net'], graph.syntax.LOCK)
        with self.assertRaises(ValueError):
            graph.audit_text(mutated, self.queries)

    def test_actual_training_net_name_is_not_an_oracle(self):
        group = next(g for g in self.actual['InternalDriverGroups'] if 'training_ctrl/' in g['NativeSource'])
        old = group['FunctionalSource']['Ports']['Q']
        mutated = self.text.replace(old + ' ', '\\camera_vga_training_reset_proof ')
        self.assertNotEqual(mutated, self.text)
        self.assertEqual(graph.audit_text(mutated, self.queries)['Status'], 'pass')

    def test_clear_function_corruption_rejected(self):
        lut = self.actual['ClearRoots'][0]['LUT']
        old = lut['Parameters']['INIT']
        anchor = '\\' + lut['Name'] + '  ('
        cell = self.text.index(anchor)
        parameter = self.text.rfind(old, 0, cell)
        self.assertGreater(parameter, 0)
        mutated = self.text[:parameter] + "64'h0000000000000000" + self.text[parameter + len(old):]
        with self.assertRaisesRegex(ValueError, 'clear LUT truth table'):
            graph.audit_text(mutated, self.queries)

    def test_failed_native_receipt_rejected(self):
        receipt = json.loads((BASE / 'work/camera-vga-output/physical-query-20261031-a/result.json').read_text())
        receipt['ExecutionPassed'] = False
        receipt['ExitCode'] = 3221225477
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'result.json'
            path.write_text(json.dumps(receipt), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'did not complete cleanly'):
                proof.read_receipt(path, receipt['Schema'], receipt['SourceADFSHA256'], {}, [])


if __name__ == '__main__':
    unittest.main()
