"""Local saved-unit fixture and rejection checks; never touch publication worktree."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
LAB = HERE.parent / 'assoc2way256-a'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


portable = load('research_portable_tested', HERE / 'verify_research_portable_a.py')
prepare = load('research_preparer_tested', HERE / 'prepare_research_archive_a.py')


class ResearchPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='finite-fixture-', dir=HERE)
        self.root = Path(self.temp.name).resolve()
        self.map_path = self.root / 'source-map.json'
        self.value = dict(Schema='tile8-cache-research-portable-map-v1', ResearchOnly=True,
                          EDAReexecuted=False, BoardOrReleaseAcceptanceConferred=False,
                          AssocCacheSource='cache.v', CapacityModel='model.py', Files=[], UnitReceipts=[], BoundaryReceipts=[])

        def add(source, target):
            destination = self.root / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            self.value['Files'].append(dict(BundlePath=target, OriginalPath=str(source),
                                            SHA256=hashlib.sha256(destination.read_bytes()).hexdigest(), Bytes=destination.stat().st_size))
        add(LAB / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v', 'cache.v')
        add(HERE.parent / 'capacity_associativity_screen_a.py', 'model.py')
        add(LAB / 'unit-c/simulation.json', 'unit/simulation.json')
        add(LAB / 'unit-c/simulation.log', 'unit/simulation.log')
        cases = []
        for width, height, bits in ((2048, 480, 5), (639, 480, 6), (1920, 1080, 10)):
            suffix = f'{width}-i{bits}'
            for kind, ext in (('trace', 'txt'), ('summary', 'json')):
                add(LAB / f'unit-c/{kind}-{suffix}.{ext}', f'unit/{kind}-{suffix}.{ext}')
            cases.append(dict(Case=suffix, Width=width, Height=height, IndexBits=bits,
                              Trace=f'unit/trace-{suffix}.txt', Summary=f'unit/summary-{suffix}.json'))
        self.value['UnitReceipts'] = [dict(Receipt='unit/simulation.json', SimulationLog='unit/simulation.log', Cases=cases)]
        add(LAB / 'boundary-a/simulation.json', 'boundary/simulation.json')
        add(LAB / 'boundary-a/commit/peer-commit-cases.csv', 'boundary/peer-commit-cases.csv')
        self.value['BoundaryReceipts'] = [dict(Receipt='boundary/simulation.json', CommitCSV='boundary/peer-commit-cases.csv')]

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.map_path.write_text(json.dumps(self.value), encoding='utf-8')

    def resign(self, name):
        path = self.root / name
        row = next(row for row in self.value['Files'] if row['BundlePath'] == name)
        row.update(Bytes=path.stat().st_size, SHA256=hashlib.sha256(path.read_bytes()).hexdigest())

    def alter_unit_bound_artifact(self, name, new_bytes):
        (self.root / ('unit/' + name)).write_bytes(new_bytes)
        self.resign('unit/' + name)
        path = self.root / 'unit/simulation.json'
        receipt = json.loads(path.read_text())
        receipt['ArtifactsSHA256'][name] = hashlib.sha256(new_bytes).hexdigest()
        path.write_text(json.dumps(receipt), encoding='utf-8')
        self.resign('unit/simulation.json')

    def reject(self):
        self.save()
        with self.assertRaises((ValueError, KeyError, TypeError)):
            portable.review(self.root, self.map_path)

    def test_real_saved_unit_fixture_and_nine_finite_lru_cases(self):
        self.save()
        result = portable.review(self.root, self.map_path)
        self.assertTrue(result['Passed'])
        self.assertEqual(len(result['SavedUnitCases']), 3)
        self.assertEqual(sum(r['Outputs'] for r in result['SavedUnitCases']), 1173)
        self.assertEqual(len(result['FiniteCapacityLRUCases']), 9)
        self.assertFalse(result['FullSystemReexecuted'])
        self.assertFalse(result['EDAReexecuted'])

    def test_paths_reject_escape_absolute_ads_backslash_and_dot(self):
        for name in ('../cache.v', '/cache.v', 'D:/cache.v', 'cache.v:stream', 'unit\\x', './cache.v', 'unit//x'):
            with self.subTest(name=name):
                original = self.value['Files'][0]['BundlePath']
                self.value['Files'][0]['BundlePath'] = name
                self.reject()
                self.value['Files'][0]['BundlePath'] = original

    def test_case_collision(self):
        self.value['Files'].append({**self.value['Files'][0], 'BundlePath': 'CACHE.V'})
        self.reject()

    def test_byte_size_drift(self):
        self.value['Files'][0]['Bytes'] += 1
        self.reject()

    def test_byte_sha_drift(self):
        self.value['Files'][0]['SHA256'] = '0' * 64
        self.reject()

    def test_missing_mapped_role(self):
        self.value['CapacityModel'] = 'not-mapped.py'
        self.reject()

    def test_old_cache_rebound_with_self_consistent_file_sha_rejected(self):
        (self.root / 'cache.v').write_text('// old cache or alternate implementation\n')
        self.resign('cache.v')
        self.reject()

    def test_model_rebound_with_self_consistent_file_sha_rejected(self):
        with (self.root / 'model.py').open('a') as out:
            out.write('\n# changed finite model\n')
        self.resign('model.py')
        self.reject()

    def test_passed_flag_cannot_replace_trace_oracle(self):
        path = self.root / 'unit/trace-1920-i10.txt'
        lines = path.read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith('O '))
        fields = lines[index].split()
        fields[1] = f'{int(fields[1], 16) ^ 1:06x}'
        lines[index] = ' '.join(fields)
        self.alter_unit_bound_artifact(path.name, ('\n'.join(lines) + '\n').encode())
        self.reject()

    def test_original_trace_binding_required(self):
        path = self.root / 'unit/trace-1920-i10.txt'
        path.write_text(path.read_text() + '\n')
        self.resign('unit/' + path.name)
        self.reject()

    def test_incomplete_cases_rejected(self):
        self.value['UnitReceipts'][0]['Cases'].pop()
        self.reject()

    def test_duplicate_geometry_cannot_stand_in_for_three_cases(self):
        self.value['UnitReceipts'][0]['Cases'][0] = copy.deepcopy(self.value['UnitReceipts'][0]['Cases'][2])
        self.reject()

    def test_boundary_role_is_required(self):
        self.value['BoundaryReceipts'] = []
        self.reject()

    def test_both_lru_victim_directions_required(self):
        path = self.root / 'unit/simulation.json'
        receipt = json.loads(path.read_text())
        receipt['Cases']['1920-i10']['AssociativeOracle']['LRUVictimWay1Choices'] = 0
        path.write_text(json.dumps(receipt))
        self.resign('unit/simulation.json')
        self.reject()

    def test_raw_summary_and_receipt_must_agree(self):
        path = self.root / 'unit/summary-1920-i10.json'
        summary = json.loads(path.read_text())
        summary['warm_span_cycles'] = 64
        self.alter_unit_bound_artifact(path.name, json.dumps(summary).encode())
        self.reject()

    def test_boundary_case_rows_required(self):
        path = self.root / 'boundary/peer-commit-cases.csv'
        path.write_text(path.read_text().replace('128,4,0', '128,4,1'))
        self.resign('boundary/peer-commit-cases.csv')
        receipt_path = self.root / 'boundary/simulation.json'
        receipt = json.loads(receipt_path.read_text())
        receipt['ArtifactsSHA256']['commit/peer-commit-cases.csv'] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt))
        self.resign('boundary/simulation.json')
        self.reject()

    def test_no_reexecution_claim_allowed(self):
        self.value['EDAReexecuted'] = True
        self.reject()

    def test_pending_evidence_cannot_be_sealed(self):
        spec = dict(Sources=[dict(Source='output/new-next-probe-20261104/no-such-completed-receipt.json',
                                  BundlePath='evidence/pending.json', Role='pending')], Evidence=[])
        with self.assertRaises(ValueError):
            prepare.build_inventory(spec, True)

    def test_old_publication_targets_and_git_are_forbidden(self):
        for name in ('.git/index', '.gitattributes', 'distortion/rtl/old.v', 'delivery/20261104-hdmi-camera-fisheye-tile8-directfill/README.md'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    prepare.target_path(name)

    def test_preflight_non_directory_parent(self):
        original_pub = prepare.PUB
        prepare.PUB = self.root
        try:
            parent = self.root / prepare.DELIVERY / 'parent'
            parent.parent.mkdir(parents=True)
            parent.write_text('not a directory')
            with self.assertRaises((ValueError, OSError)):
                prepare.target_path(prepare.DELIVERY + '/parent/child.txt')
        finally:
            prepare.PUB = original_pub

    def test_preflight_planned_file_parent_conflict(self):
        with self.assertRaises(ValueError):
            prepare.preflight_names([prepare.DELIVERY + '/a', prepare.DELIVERY + '/a/b'])
        with self.assertRaises(ValueError):
            prepare.preflight_names([prepare.DELIVERY + '/a', prepare.DELIVERY + '/A'])

    def safe_guard_fixture(self, poison=None):
        fifo = HERE.parent / 'assoc2way256-fifo-a'
        spec = json.loads((HERE / 'research-archive-spec-a.json').read_text())
        value = json.loads((fifo / 'system-sustained-small-b/simulation.json').read_text())
        proof = json.loads((fifo / 'bench-safe-stop-transformation-a.json').read_text())
        data = Path(proof['NewBench']['Path']).read_bytes()
        if poison == 'clock':
            self.assertIn(b'always #4', data)
            data = data.replace(b'always #4', b'always #5', 1)
        elif poison == 'assertion':
            self.assertIn(b'bad scan completion outside deliberate small fault phase', data)
            data = data.replace(b'bad scan completion outside deliberate small fault phase',
                                b'bad scan completion outside deliberate small fault phasX', 1)
        bench = self.root / 'native-safe-bench.sv'
        bench.write_bytes(data)
        proof['NewBench'] = dict(Path=str(bench), SHA256=hashlib.sha256(data).hexdigest())
        proof_path = self.root / 'safe-proof.json'
        proof_path.write_text(json.dumps(proof))
        for row in spec['Sources']:
            if row['Role'] == 'safe-stop-bench-safe-stop-transformation-a':
                row['Source'] = proof_path.relative_to(prepare.REPO).as_posix()
        return spec, value

    def test_real_safe_stop_exact_source_guard(self):
        spec, value = self.safe_guard_fixture()
        watched = {}
        self.assertTrue(prepare.verify_safe_stop_clock_basis(spec, value, watched))
        self.assertEqual(len(watched), 4)

    def test_extra_clock_change_rejected_even_after_resigning_proof(self):
        spec, value = self.safe_guard_fixture('clock')
        with self.assertRaises(ValueError):
            prepare.verify_safe_stop_clock_basis(spec, value, {})

    def test_extra_assertion_character_rejected_after_resigning_proof(self):
        spec, value = self.safe_guard_fixture('assertion')
        with self.assertRaises(ValueError):
            prepare.verify_safe_stop_clock_basis(spec, value, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
