"""LIVE validation branch with fake transport only; never a device measurement.

Reference files are read as actual bytes. The attestation is serialized once;
the same bytes supply parsed inputs and capture hashes. No serial import/open,
disk capture, real waiting, programming or physical load receipt is involved.
"""
from pathlib import Path
import copy
import hashlib
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from collect_measurement import CaptureSession
from measurement_report import analyze_run
from test_collect_measurement import Clock, Sink, Transport
import fixture_packets as fixtures


def sha(data):
    return hashlib.sha256(data).hexdigest()


class LiveMetadataBindingTests(unittest.TestCase):
    def fixture(self):
        input_bytes = {
            "manifest": (ROOT / "reference/MEASUREMENT_BUILD_MANIFEST.json").read_bytes(),
            "plan": (ROOT / "reference/canonical-requests/PLAN.json").read_bytes(),
        }
        manifest = json.loads(input_bytes["manifest"].decode("utf-8-sig"))
        plan = json.loads(input_bytes["plan"].decode("utf-8-sig"))
        attestation = dict(
            loaded_firmware_sha256=manifest["firmware_sha256"],
            load_receipt_evidence="OFFLINE fake LIVE-branch schema fixture, not a real load receipt",
            epoch_label="OFFLINE_LIVE_SCHEMA_TEST_NOT_DEVICE", uninterrupted_reset_epoch=True,
            known_packet_boundary_offset=0,
            boundary_evidence="Offline concatenation boundary; no physical observation",
            input_description="OFFLINE serialized fake packets, not a camera or board")
        input_bytes["run_attestation"] = json.dumps(attestation, sort_keys=True).encode("utf-8")
        attestation = json.loads(input_bytes["run_attestation"].decode("utf-8-sig"))
        first = dict(ticks=(1 << 32) - 100000000, sequence=17, frame_id=2000,
                     counts=(401, 400, 350, 100, 2), raw_cycles=6249999)
        last = dict(ticks=first["ticks"] + 2500000000, sequence=18, frame_id=2400,
                    counts=(801, 800, 650, 400, 4), raw_cycles=6374999)
        clock, sink = Clock(), Sink()
        transport = Transport(clock,
            fixtures.ack() + fixtures.signature(),
            fixtures.stat(0, **first) + fixtures.signature(frame_id=2001),
            fixtures.signature(frame_id=2400) + fixtures.stat(1, **last) + b"PGSIG001\x01")
        # Deliberately exercise LIVE schema rules using ONLY injected fakes.
        session = CaptureSession(transport, sink, plan, manifest, attestation,
                                 capture_kind="LIVE_SERIAL_CAPTURE", clock=clock)
        session.meta.update(
            manifest_sha256=sha(input_bytes["manifest"]),
            plan_sha256=sha(input_bytes["plan"]),
            run_attestation_sha256=sha(input_bytes["run_attestation"]))
        meta = session.run()
        raw = bytes(sink.raw)
        meta["raw_sha256"] = sha(raw)
        self.assertEqual(meta["outcome"], "CAPTURE_COMPLETE_TWO_SNAPSHOTS")
        self.assertEqual(transport.writes, [bytes.fromhex(c["Hex"]) for c in plan["Commands"]])
        self.assertFalse(transport.is_open)
        self.assertNotIn("serial", sys.modules)
        return raw, manifest, plan, attestation, meta, input_bytes

    def report(self, data):
        raw, manifest, plan, attestation, meta, input_bytes = data
        return analyze_run(raw, manifest, plan, attestation, meta, input_file_bytes=input_bytes)

    def reject_tamper(self, field, value):
        data = list(self.fixture())
        data[4] = copy.deepcopy(data[4])
        data[4][field] = value
        with self.assertRaises(ValueError):
            self.report(data)

    def test_baseline_fake_LIVE_exact_input_bytes(self):
        result = self.report(self.fixture())
        # The status is the branch classification; this test uses fake data only.
        self.assertEqual(result["status"], "PASS_VALIDATED_INTERNAL_COUNTER_RUN")
        self.assertEqual(result["core_window"]["seconds_nominal"], 20)

    def test_loaded_firmware_metadata_tamper_rejected(self):
        self.reject_tamper("loaded_firmware_sha256", "0" * 64)

    def test_epoch_label_metadata_tamper_rejected(self):
        self.reject_tamper("epoch_label", "TAMPERED_EPOCH_LABEL")

    def test_manifest_file_hash_metadata_tamper_rejected(self):
        self.reject_tamper("manifest_sha256", "0" * 64)

    def test_attestation_file_hash_metadata_tamper_rejected(self):
        self.reject_tamper("run_attestation_sha256", "0" * 64)

    def test_plan_file_hash_metadata_tamper_rejected(self):
        self.reject_tamper("plan_sha256", "0" * 64)

    def test_reset_epoch_metadata_false_rejected(self):
        self.reject_tamper("uninterrupted_reset_epoch_attested", False)


if __name__ == "__main__":
    unittest.main()
