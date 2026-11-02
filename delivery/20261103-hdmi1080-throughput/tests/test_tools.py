"""Pure CPU checks for source isolation and the existing scan-wire protocol."""
from pathlib import Path
import importlib.util
import struct
import unittest
from unittest.mock import patch
import copy
import shutil
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scan = load('analyze_scan')
prep = load('prepare_candidate')
delivery = load('verify_delivery')


def packet(frame=1, seq=0, epoch=1, mode=1, crc=100, param=0x1234, session=8, dropped=0):
    data = bytearray(128)
    data[:8] = b'PGSIG001'
    data[8:15] = b'\x01\x02\x01\x01\x80\x00\x08'
    struct.pack_into('<10I', data, 16, session, epoch, frame, param, seq, 1920 * 1080,
                     crc, dropped, 0, 0)
    struct.pack_into('<HHBB', data, 56, 1920, 1080, 255, mode)
    struct.pack_into('<I', data, 120, zlib.crc32(data[:120]))
    data[124:] = b'SG01'
    return bytes(data)


class ScanTests(unittest.TestCase):
    def result(self, blob, **kwargs):
        return scan.analyze(blob, 1.0, 0x1234, 8, **kwargs)

    def test_repeated_display_is_not_new_frame(self):
        result = self.result(b'ACK' + packet() + packet(seq=1, epoch=2)
                             + packet(frame=2, seq=2, epoch=3, crc=101))
        self.assertTrue(result['valid_fixed_correction_window'])
        self.assertEqual(result['accepted_unique_display_fps'], 2)
        self.assertEqual(result['repeat_scan_records'], 1)

    def test_mixed_mode_cannot_be_reported_as_pure_correction(self):
        result = self.result(packet() + packet(frame=2, seq=1, epoch=2, mode=0))
        self.assertFalse(result['valid_fixed_correction_window'])
        self.assertIsNone(result['accepted_unique_display_fps'])

    def test_crc_corruption_gap_identity_and_observer_errors(self):
        corrupt = bytearray(packet())
        corrupt[70] ^= 1
        cases = [bytes(corrupt), packet(seq=2), packet(param=4), packet(session=9),
                 packet(dropped=1), packet(crc=200), packet(epoch=3, seq=1)]
        for bad in cases:
            with self.subTest(bad=bad):
                self.assertFalse(self.result(packet() + bad)['valid_fixed_correction_window'])

    def test_truncated_final_packet_is_reported(self):
        result = self.result(packet() + packet(seq=1, epoch=2) + packet()[:40])
        self.assertEqual(result['trailing_partial_packet_bytes'], 40)
        self.assertTrue(result['valid_fixed_correction_window'])

    def test_invalid_window_rejected(self):
        for duration in (0, -1, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                scan.analyze(b'', duration, 0x1234, 8)

    def test_reference_newlines_preserve_content_identity(self):
        lf = b'line1\nline2\n'
        crlf = lf.replace(b'\n', b'\r\n')
        digest = prep.sha(crlf)
        self.assertTrue(delivery.reference_text_matches(lf, digest))
        self.assertTrue(delivery.reference_text_matches(crlf, digest))
        self.assertFalse(delivery.reference_text_matches(b'changed\nline2\n', digest))


class SourceTests(unittest.TestCase):
    def test_baseline_only_changes_mode_control_and_identity(self):
        manifest, sources, identity = prep.candidate_sources('baseline', 'corrected')
        changed = set()
        for row in manifest['files']:
            if row['disposition'] == 'included_source':
                if sources[row['path']] != (prep.BASE / 'native' / row['path']).read_bytes():
                    changed.add(row['path'])
        self.assertEqual(changed, {prep.SELECTOR, prep.TOP})
        self.assertIn(b'parameter integer MODE=1', sources[prep.SELECTOR])
        self.assertEqual(identity['mode'], 'corrected')

    def test_modes_have_separate_identity_and_keep_closure(self):
        outputs = [prep.candidate_sources('baseline', mode) for mode in ('raw', 'corrected', 'demo')]
        self.assertEqual(len({r[2]['param_id_hex'] for r in outputs}), 3)
        self.assertEqual(set(outputs[0][1]), set(outputs[1][1]))

    def test_missing_dependencies_fail_before_writing(self):
        name = 'unit-missing-dependencies'
        self.assertFalse((ROOT / '_build' / name).exists())
        with self.assertRaises(ValueError):
            prep.prepare(ROOT / 'no-such-dependency-tree', name, 'baseline')
        self.assertFalse((ROOT / '_build' / name).exists())

    def test_run_name_cannot_escape_output(self):
        with self.assertRaises(ValueError):
            prep.prepare('.', '../escape', 'baseline')

    def test_complete_preparation_with_synthetic_external_dependencies(self):
        # Exercise source relocation/selection without claiming vendor source
        # availability. Every external row is explicitly replaced by a fixture.
        manifest = copy.deepcopy(prep.frozen_manifest())
        fixture = b'// Synthetic dependency for preparation unit test only.\n'
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory)
            deps, candidate = task / 'deps', task / 'candidate'
            (candidate / 'rtl').mkdir(parents=True)
            for name in ('frame_ab_control.v', 'ddr_adaptive_result_writer.v',
                         'ddr_compact_neighbour_cache_scatter4.v'):
                shutil.copyfile(ROOT / 'rtl' / name, candidate / 'rtl' / name)
            for row in manifest['files']:
                if row['disposition'] != 'included_source':
                    target = deps / row['path']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(fixture)
                    row['sha256'], row['bytes'] = prep.sha(fixture), len(fixture)
            with patch.object(prep, 'ROOT', candidate), patch.object(prep, 'frozen_manifest', return_value=manifest):
                output_root = task / 'o'
                result = prep.prepare(deps, 'test', 'both', 'corrected', output_root)
                self.assertEqual(result['source_count'], 130)
                work = output_root / 'test'
                writer = (work / 'native' / prep.WRITER).read_text()
                self.assertNotIn('`include "video_crc32.vh"', writer)
                self.assertIn((work / 'native/source/rtl/video_crc32.vh').resolve().as_posix(), writer)
                self.assertIn(result['param_id_hex'], (work / 'native' / prep.TOP).read_text())
                with self.assertRaises(FileExistsError):
                    prep.prepare(deps, 'test', 'both', output_root=output_root)
                dependency = next(row for row in manifest['files'] if row['disposition'] != 'included_source')
                (deps / dependency['path']).write_bytes(b'corrupt')
                with self.assertRaises(ValueError):
                    prep.prepare(deps, 'hash-fail', 'both', output_root=output_root)
                self.assertFalse((output_root / 'hash-fail').exists())

    def test_deep_output_path_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / ('x' * 150)
            with self.assertRaisesRegex(ValueError, 'output-root'):
                prep.prepare('.', 'deep', 'baseline', output_root=output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
