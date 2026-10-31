"""Reject false completeness and changes outside the two orientation writes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_ov5640_cadence_upright_sim as candidate


class UprightOracleTests(unittest.TestCase):
    def setUp(self):
        self.words = candidate.base_commands()
        self.sequence = candidate.expected_case(self.words, 0, 0)
        self.rows = [(item, i * 20 + 1, i * 20 + 10) for i, item in enumerate(self.sequence)]

    def test_exact_counts_and_only_two_baseline_deltas(self):
        self.assertEqual(candidate.validate_trace(self.rows, self.sequence), 311)
        writes = [item for item in self.sequence if item[0] == "W"]
        deltas = [i for i, (item, word) in enumerate(zip(writes, self.words))
                  if (item[1], item[2]) != (word >> 16, (word >> 8) & 255)]
        self.assertEqual(deltas, [40, 41])
        self.assertEqual(len(writes), 264)
        self.assertEqual(writes[245][1:3], (0x3008, 2))

    def test_mandatory_reads_when_generic_checker_disabled(self):
        seq = candidate.expected_case(self.words, 1, 0)
        self.assertEqual(len(seq), 286)
        immediate = [item[1] for item in seq if item[0] == "R" and item[4] == 1]
        self.assertEqual(immediate, [0x3820, 0x3821])
        self.assertEqual([i[2] for i in seq if i[0] == "W" and i[1] == 0x3018], [0x34])

    def test_missing_orientation_read_rejected(self):
        rows = [row for row in self.rows if not (row[0][0] == "R" and row[0][1] == 0x3821 and row[0][4] == 1)]
        with self.assertRaises(ValueError):
            candidate.validate_trace(rows, self.sequence)

    def test_nonorientation_write_corruption_rejected(self):
        rows = self.rows.copy()
        index = next(i for i, row in enumerate(rows) if row[0][0] == "W" and row[0][1] == 0x3035)
        item, start, stop = rows[index]
        rows[index] = ((item[0], item[1], item[2] ^ 1, *item[3:]), start, stop)
        with self.assertRaises(ValueError):
            candidate.validate_trace(rows, self.sequence)

    def test_retry_restarts_complete_nine_register_check(self):
        seq = candidate.expected_case(self.words, 0, 4)
        self.assertEqual([i[1:3] for i in seq if i[4] == 4], candidate.VERIFY)
        self.assertEqual(sum(i[0] == "W" for i in seq), 264)
        self.assertEqual(len(seq), 319)

    def test_prefinal_failure_has_no_final_write(self):
        seq = candidate.expected_case(self.words, 0, 3)
        self.assertEqual(sum(i[0] == "W" for i in seq), 263)
        self.assertEqual(seq[-1], ("R", 0x3820, 1, 1, 2, -1))

    def test_reordered_and_duplicate_transactions_rejected(self):
        rows = self.rows.copy()
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaises(ValueError):
            candidate.validate_trace(rows, self.sequence)
        with self.assertRaises(ValueError):
            candidate.validate_trace(self.rows + self.rows[-1:], self.sequence)


if __name__ == "__main__":
    unittest.main()
