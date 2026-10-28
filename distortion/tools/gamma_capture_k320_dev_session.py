"""Finite source-bound R1 triplet SRAM session. Default plan; explicit execute."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import threading
import time
import uuid
import zlib

import build_gamma_capture_k320_dev as builder
import prepare_gamma_capture_k320_dev as candidate
import read_gamma_capture_k320_dev as reader
import program_native_raw as hw
import program_idle_heartbeat as idle

ROOT, TARGET, APPROVED = candidate.ROOT, "gamma_capture_k320_dev", builder.APPROVED
BAUD, MAX_RX_BYTES = 921600, 12 * 1024 * 1024
PACKET_BYTES = 614400 + 44
TRIPLET_BYTES = 3 * PACKET_BYTES


def helpers():
    names = ("gamma_capture_k320_dev_session.py", "build_gamma_capture_k320_dev.py",
             "prepare_gamma_capture_k320_dev.py", "gamma_capture_k320_dev_evidence.py",
             "read_gamma_capture_k320_dev.py", "frozen_gamma_analysis.py", "evaluate-tone-pair.py",
             "frame_protocol.py", "gamma_triplets.py", "program_native_raw.py", "program_idle_heartbeat.py",
             "native_camera_capture.py", "camera_eye_pin_audit.py")
    return {"tools/" + name: hw.sha(ROOT / "tools" / name) for name in names}


def limits(port, seconds, frequency):
    if port != "COM5":
        raise ValueError("this controlled physical session supports only explicit COM5")
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 30 <= seconds <= 60:
        raise ValueError("post-DONE observation must be finite30..60seconds (default45)")
    if frequency not in ("1MHz", "5MHz"):
        raise ValueError("only1MHz/5MHz SRAM programming is supported")


def validate_target(build_dir):
    work = Path(build_dir).resolve()
    if not work.is_dir() or not work.is_relative_to(APPROVED.resolve()):
        raise ValueError("existing fixed debug build under approved scratch required")
    manifest_path, result_path = work / "validated-build.json", work / "build-result.json"
    manifest, result = builder.load(manifest_path), builder.load(result_path)
    if (result.get("Passed") is not True or type(result.get("ProcessExitCode")) is not int
            or result["ProcessExitCode"] != 0 or result.get("TimedOut") is not False
            or result.get("ValidatedBuildSHA256") != hw.sha(manifest_path)):
        raise ValueError("successful native offline build result is required")
    before, simulation = builder.verify_prepared(), builder.validate_simulation()
    if builder.validate_artifacts(work, before, simulation) != manifest:
        raise ValueError("canonical debug source/bit/timing/pin/simulation proof differs")
    if result.get("SourceSHA256") != before["SourceSHA256"] or result.get("SourceSHA256After") != before["SourceSHA256"]:
        raise ValueError("native build result source closure differs")
    bit = work / "generate_bitstream" / (TARGET + ".sbit")
    if Path(manifest["Bitstream"]).resolve() != bit:
        raise ValueError("only the fixed named debug SRAM bitstream is eligible")
    return {"target": TARGET, "build_dir": str(work), "manifest_path": str(manifest_path),
            "manifest_sha256": hw.sha(manifest_path), "build_result_sha256": hw.sha(result_path),
            "bitstream_path": str(bit), "bitstream_sha256": manifest["SHA256"].lower(),
            "source_sha256": before["SourceSHA256"], "profile_binding": before["ProfileBinding"],
            "simulation_evidence": simulation, "pin_count": 128,
            "capture_role": "one_shot_same_source_raw_bypass_gamma", "protocol": "PGFRAME1", "baud": BAUD}


def validate_connection(path, binding):
    path = Path(path).resolve()
    record = hw.load_json(path)
    identity = binding["Identity"]
    reviews = record.get("connection_review", {})
    if (record.get("eye") != "CAM2" or record.get("image_size") != [640, 480]
            or record.get("pixel_format") != "RGB565_LE"
            or any(record.get(key) != value for key, value in identity.items())
            or any(reviews.get(key) is not True for key in
                   ("new_module_pinout_verified", "power_and_io_verified", "selected_eye_verified"))):
        raise ValueError("CAM2 documentary connection review and exact four source identities required")
    basis = record.get("connection_review_basis", {})
    review = basis.get("review_record", {})
    review_path = Path(review.get("path", ""))
    review_path = (review_path if review_path.is_absolute() else path.parent / review_path).resolve()
    if not review_path.is_file() or hw.sha(review_path) != review.get("sha256"):
        raise ValueError("documentary connection review source is missing or changed")
    return {"path": str(path), "sha256": hw.sha(path), "identity": identity, "eye": "CAM2",
            "review_record_path": str(review_path), "review_record_sha256": hw.sha(review_path),
            "review_basis": basis, "semantics": "documentary/operator engineering review only; old build and programmed flag are not inherited",
            "HardwareIdentityVerifiedOnWire": False, "CalibrationTransferAccepted": False}


def check_scripts(plan, factory=hw._scripts):
    work = Path(plan["workdir"]).resolve()
    for stage, text in factory(plan["validation"], plan["frequency"]).items():
        record = plan["tcl"][stage]
        path = Path(record["path"]).resolve()
        if path != work / (stage + ".tcl") or path.read_text(encoding="utf-8") != text or hw.sha(path) != record["sha256"]:
            raise ValueError("fixed volatile SRAM Tcl differs")


def prepare_plan(build_dir, workdir, *, connection_binding, port="COM5", seconds=45., frequency="5MHz", pds_bin=None):
    limits(port, seconds, frequency)
    base = Path(workdir).resolve()
    if not base.is_dir() or not base.is_relative_to(APPROVED.resolve()):
        raise ValueError("existing approved scratch parent required")
    validation = validate_target(build_dir)
    connection = validate_connection(connection_binding, validation["profile_binding"])
    idle.validate_heartbeat()
    pds = hw.resolve_pds_bin(pds_bin)
    work = base / ("gamma-k320-session-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8])
    work.mkdir(exist_ok=False)
    program = work / "candidate-program"
    program.mkdir(exist_ok=False)
    scripts = hw._scripts(validation, frequency)
    for stage, text in scripts.items():
        with (program / (stage + ".tcl")).open("x", encoding="utf-8") as out:
            out.write(text)
    nested = {"target": TARGET, "operation": "volatile_sram_only", "workdir": str(program),
              "frequency": frequency, "pds_bin": str(pds), "validation": validation,
              "tcl": {stage: {"path": str(program / (stage + ".tcl")), "sha256": hw.sha(program / (stage + ".tcl"))} for stage in scripts}}
    plan = {"schema": 1, "target": TARGET, "operation": "finite_k320_one_shot_then_fixed_heartbeat",
            "executed": False, "hardware_accessed": False, "requires_explicit_execute_flag": True,
            "workdir": str(work), "port": port, "baud": BAUD, "seconds_after_done": seconds,
            "frequency": frequency, "group_seed": candidate.GROUP_SEED, "connection_review": connection,
            "program_plan": nested, "idle_plan": idle.prepare_plan(work, pds_bin=pds, frequency=frequency),
            "helper_sha256": helpers(), "DevelopmentOnly": True, "CalibrationAccepted": False,
            "HardwareReleaseAllowed": False, "HardwareIdentityVerifiedOnWire": False,
            "limits": "Open RX before cfg_program; quarantine until successful source-bound programming and fresh DONE. CRC/seed are transaction labels, not camera authentication. Numeric replay and physical UART evidence are separate. Finally fixed heartbeat required."}
    hw._new_json(work / "plan.json", plan)
    return plan


def check_program(plan):
    if (plan.get("target") != TARGET or plan.get("operation") != "volatile_sram_only"
            or plan.get("frequency") not in ("1MHz", "5MHz")
            or validate_target(plan["validation"]["build_dir"]) != plan["validation"]):
        raise ValueError("fixed R1 source-bound SRAM program plan changed")
    check_scripts(plan)


def execute_program(plan, *, before_program=None):
    owned, work = [], Path(plan["workdir"])
    result = {"schema": 1, "target": TARGET, "operation": "volatile_sram_only", "passed": False,
              "hardware_accessed": False, "programming_attempted": False, "done_confirmed": False,
              "workdir": str(work), "bitstream_sha256": plan["validation"]["bitstream_sha256"]}
    try:
        check_program(plan)
        if (work / "receipt.json").exists() or hw.listening_pids(hw.PORT):
            raise RuntimeError("used plan or occupied JTAG listener; no foreign server is used/stopped")
        pds = Path(plan["pds_bin"])
        server = hw._start_owned([str(pds / "cdt_js.exe"), "-port", str(hw.PORT), "-work_dir", str(work)], work, owned, "server")
        result["hardware_accessed"] = True
        hw._await_owned_server(server)
        hw._owned_server_check(server)
        hw._check_scan(hw._client(plan, "scan", owned, 90.))
        check_program(plan)
        previous = server
        server = hw._program_server_after_scan(server, plan, owned)
        result["server_restarted_after_scan"] = server is not previous
        if before_program is not None:
            before_program()
        result["programming_attempted"] = True
        hw._check_program(hw._client(plan, "program", owned, 90.))
        check_program(plan)
        result.update(passed=True, done_confirmed=True)
    except (Exception, KeyboardInterrupt) as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        result["owned_pids"] = [p.pid for p in owned]
        result["terminated_owned_pids"], result["cleanup_errors"] = hw._stop_owned(owned)
        if result["cleanup_errors"]:
            result["passed"] = False
        result["logs"] = {str(p): hw.sha(p) for p in work.glob("*.log")}
        result["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
        hw._new_json(work / "receipt.json", result)
    return result


class RXDrain:
    """Bounded, receive-only thread; preserve all bytes before and during PDS."""
    def __init__(self, link, work, *, clock=time.monotonic):
        self.link, self.work, self.clock = link, Path(work), clock
        self.lock, self.stopping = threading.Lock(), threading.Event()
        self.data, self.markers = bytearray(), {}
        self.phase, self.error = "preprogram_quarantine", None
        self.thread = threading.Thread(target=self._run, name="k320-uart-rx", daemon=True)

    def start(self):
        self.thread.start()

    def mark(self, phase):
        with self.lock:
            self.phase = phase
            record = {"offset": len(self.data), "monotonic": self.clock(), "utc": datetime.now(timezone.utc).isoformat()}
            self.markers[phase] = record
            return dict(record)

    def _run(self):
        try:
            with (self.work / "rx-all.bin").open("xb") as wire, (self.work / "rx-events.jsonl").open("x", encoding="utf-8") as events:
                while not self.stopping.is_set():
                    block = self.link.read(65536)
                    if not block:
                        continue
                    with self.lock:
                        if len(self.data) + len(block) > MAX_RX_BYTES:
                            raise RuntimeError("bounded RX quarantine exceeded12MiB")
                        start = len(self.data)
                        self.data.extend(block)
                        wire.write(block)
                        events.write(json.dumps({"offset": start, "bytes": len(block), "phase": self.phase,
                                                 "monotonic": self.clock(), "utc": datetime.now(timezone.utc).isoformat()}) + "\n")
        except BaseException as exc:
            if not self.stopping.is_set():
                self.error = type(exc).__name__ + ": " + str(exc)

    def snapshot(self):
        with self.lock:
            return bytes(self.data)

    def close(self):
        self.stopping.set()
        error = None
        try:
            self.link.close()
        except BaseException as exc:
            error = exc
        finally:
            self.thread.join(timeout=2.)
        if self.thread.is_alive():
            raise RuntimeError("owned RX thread did not stop before heartbeat")
        if error is not None:
            raise RuntimeError("serial close failed after RX thread joined: " + str(error)) from error


def extract_triplet(data, start):
    """Only pre-seed bytes can be quarantined; selected packets stay contiguous."""
    if type(data) is not bytes or type(start) is not int or not 0 <= start <= len(data):
        raise ValueError("bounded RX bytes/start offset required")
    # Begin at the full RX stream's packet boundaries, even when the program
    # marker fell in an older packet. Never start a magic search in its pixels.
    offset = 0
    while True:
        offset = data.find(b"PGFRAME1", offset)
        if offset < 0 or len(data) - offset < 32:
            raise ValueError("new-seed raw packet not received completely")
        _, width, height, ident, count, source_crc, fmt, header_crc = struct.unpack("<8sHHIIIII", data[offset:offset + 32])
        valid_header = (0 < width <= 1920 and 0 < height <= 1080 and count == width * height * 2
                        and fmt == 0x5651 and zlib.crc32(data[offset:offset + 28]) == header_crc)
        total, valid_packet = count + 44, False
        if valid_header and len(data) - offset >= total:
            payload = data[offset + 32:offset + 32 + count]
            trailer = data[offset + 32 + count:offset + total]
            valid_packet = (trailer[:8] == b"PGEND001" and struct.unpack("<I", trailer[8:])[0] == source_crc
                            and zlib.crc32(payload) == source_crc)
        if ident >> 4 == candidate.GROUP_SEED:
            if offset < start:
                if valid_packet:
                    raise ValueError("CRC-valid same-seed packet began before programming window; physical attribution is ambiguous")
                offset += 1
                continue
            if (ident != candidate.GROUP_SEED << 4 or width != 640 or height != 480 or count != 614400
                    or fmt != 0x5651 or zlib.crc32(data[offset:offset + 28]) != header_crc):
                raise ValueError("new-seed raw header/order/shape/CRC differs")
            break
        # A valid old packet is an indivisible quarantine object. RGB565 bytes
        # may contain PGFRAME1, so never search inside its CRC-valid payload.
        if valid_packet:
            offset += total
            continue
        offset += 1
    end = offset + TRIPLET_BYTES
    if len(data) < end:
        raise ValueError("incomplete one-shot three-packet stream")
    if len(data) != end:
        raise ValueError("extra RX bytes after the one-shot triplet")
    wire = data[offset:end]
    record, images, triplet = reader.check_wire(wire)
    if record.get("passed") is not True:
        raise ValueError("same-source geometry/Gamma numerical comparison failed")
    return wire, record, {"quarantined_prefix_bytes": offset, "program_window_prefix_bytes": offset - start,
                          "triplet_offset": offset, "triplet_bytes": len(wire), "extra_bytes": 0}


def serial_open(port):
    import serial
    link = serial.Serial(port=None, baudrate=BAUD, timeout=.05, write_timeout=.2, rtscts=False, dsrdtr=False)
    try:
        link.dtr = False
        link.rts = False
        link.port = port
        link.open()
        if hasattr(link, "set_buffer_size"):
            link.set_buffer_size(rx_size=1024 * 1024)
    except BaseException:
        link.close()
        raise
    return link


def verify_plan(plan):
    limits(plan["port"], plan["seconds_after_done"], plan["frequency"])
    work = Path(plan["workdir"]).resolve()
    if (not work.is_dir() or not work.is_relative_to(APPROVED.resolve()) or (work / "result.json").exists()
            or hw.load_json(work / "plan.json") != plan or helpers() != plan["helper_sha256"]
            or plan.get("target") != TARGET or plan.get("operation") != "finite_k320_one_shot_then_fixed_heartbeat"
            or plan.get("baud") != BAUD or plan.get("group_seed") != candidate.GROUP_SEED):
        raise ValueError("fresh fixed source-bound session plan required")
    check_program(plan["program_plan"])
    if (Path(plan["program_plan"]["workdir"]).resolve() != work / "candidate-program"
            or plan["program_plan"].get("frequency") != plan["frequency"]
            or (work / "candidate-program/receipt.json").exists()
            or validate_connection(plan["connection_review"]["path"], plan["program_plan"]["validation"]["profile_binding"]) != plan["connection_review"]):
        raise ValueError("candidate plan/connection review changed")
    exit_plan = plan["idle_plan"]
    if (exit_plan.get("target") != "heartbeat" or exit_plan.get("operation") != "volatile_sram_only"
            or exit_plan["frequency"] != plan["frequency"]
            or not Path(exit_plan["workdir"]).resolve().is_relative_to(work)
            or (Path(exit_plan["workdir"]) / "receipt.json").exists()
            or idle.validate_heartbeat() != exit_plan["validation"]):
        raise ValueError("source-bound fixed heartbeat exit required")
    check_scripts(exit_plan, idle._scripts)
    return work


def execute_plan(plan, *, programmer=None, serial_factory=None, restorer=None, clock=time.monotonic, sleeper=time.sleep):
    work = verify_plan(plan)
    programmer, serial_factory, restorer = programmer or execute_program, serial_factory or serial_open, restorer or idle.execute_plan
    drain, link, entered = None, None, False
    result = {"schema": 1, "target": TARGET, "passed": False, "executed": True, "hardware_accessed": False,
              "program": None, "numeric_replay": None, "idle_program": None, "idle_done_confirmed": False,
              "DevelopmentOnly": True, "CalibrationAccepted": False, "HardwareReleaseAllowed": False,
              "HardwareIdentityVerifiedOnWire": False, "CalibrationTransferAccepted": False,
              "SourceBoundPhysicalUARTObservation": False, "workdir": str(work)}
    try:
        entered = True
        link = serial_factory(plan["port"])
        drain = RXDrain(link, work, clock=clock)
        drain.start()
        drain.mark("preprogram_quarantine")
        # COM is already being drained while scan/program execute. Frames remain
        # quarantined until this invocation has a valid fresh DONE receipt.
        result["program"] = programmer(plan["program_plan"], before_program=lambda: drain.mark("program_window_quarantine"))
        active = result["program"]
        if (not isinstance(active, dict) or active.get("programming_attempted") is not True
                or active.get("passed") is not True or active.get("done_confirmed") is not True
                or active.get("target") != TARGET or active.get("bitstream_sha256") != plan["program_plan"]["validation"]["bitstream_sha256"]
                or hw.load_json(work / "candidate-program/receipt.json") != active):
            raise RuntimeError("source-bound candidate SRAM/fresh DONE receipt unconfirmed; RX stays quarantined")
        check_program(plan["program_plan"])
        if helpers() != plan["helper_sha256"] or "program_window_quarantine" not in drain.markers:
            raise ValueError("helpers changed or cfg_program boundary not recorded")
        done = drain.mark("source_bound_done_confirmed")
        deadline = clock() + plan["seconds_after_done"]
        while clock() < deadline:
            if drain.error:
                raise RuntimeError(drain.error)
            sleeper(min(.05, max(0., deadline - clock())))
        drain.close()
        link = None
        if drain.error:
            raise RuntimeError(drain.error)
        check_program(plan["program_plan"])
        if helpers() != plan["helper_sha256"]:
            raise ValueError("helpers changed during physical RX")
        data = drain.snapshot()
        start = drain.markers["program_window_quarantine"]["offset"]
        wire, numeric, selection = extract_triplet(data, start)
        if selection["triplet_offset"] + len(wire) <= done["offset"]:
            raise ValueError("entire triplet preceded fresh DONE confirmation; retain quarantine, do not attest new physical readback")
        with (work / "triplet-wire.bin").open("xb") as out:
            out.write(wire)
        result["numeric_replay"] = reader.save_replay(wire, work / "triplet")
        result["physical_uart_observation"] = {"received_bytes": len(data), "rx_all_sha256": hw.sha(work / "rx-all.bin"),
            "rx_events_sha256": hw.sha(work / "rx-events.jsonl"), "selection": selection,
            "markers": drain.markers, "bytes_received_before_done": done["offset"],
            "triplet_completed_after_done_confirmation": True,
            "program_window_marker_scope": "host callback before cfg_program client, not an on-wire configure timestamp",
            "post_done_observation_seconds": plan["seconds_after_done"], "uart_tx_bytes": 0,
            "protocol": "PGFRAME1", "capture_role": "one_shot_same_source_raw_bypass_gamma", "selected_eye": "CAM2",
            "profile_identity": plan["program_plan"]["validation"]["profile_binding"]["Identity"],
            "group_seed": candidate.GROUP_SEED, "source_bound_program_receipt": str(work / "candidate-program/receipt.json"),
            "source_bound_program_receipt_sha256": hw.sha(work / "candidate-program/receipt.json"),
            "HardwareIdentityVerifiedOnWire": False, "same_source_basis": "frozen source-bound RTL plus full-pixel comparison with raw packet; CRC/seed alone do not authenticate camera or exposure"}
        result["SourceBoundPhysicalUARTObservation"] = True
        hw._new_json(work / "physical-uart-observation.json", result["physical_uart_observation"])
    except (Exception, KeyboardInterrupt) as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        if drain is not None and link is not None:
            try:
                drain.close()
                link = None
            except BaseException as exc:
                result["serial_close_error"] = str(exc)
        elif link is not None:
            try:
                link.close()
            except BaseException as exc:
                result["serial_close_error"] = str(exc)
        if entered:
            if result["program"] is None:
                result["programming_state_unknown"] = True
            result["idle_restoration_attempted"] = True
            try:
                result["idle_program"] = restorer(plan["idle_plan"], timeout_seconds=30.)
                result["idle_done_confirmed"] = bool(result["idle_program"].get("passed") is True and result["idle_program"].get("done_confirmed") is True)
            except (Exception, KeyboardInterrupt) as exc:
                result["idle_error"] = type(exc).__name__ + ": " + str(exc)
        result["hardware_accessed"] = bool(entered and (result.get("program") or result.get("idle_program") or drain is not None))
        result["passed"] = bool(result["SourceBoundPhysicalUARTObservation"] and result["numeric_replay"]
                                and result["numeric_replay"].get("passed") is True and result["idle_done_confirmed"]
                                and not any(key in result for key in ("error", "serial_close_error", "idle_error")))
        result["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
        result["limits"] = candidate.LIMITS + " Physical UART observation is source-bound to this cfg_program/DONE event, not a wire-level sensor identity. Numeric replay keeps its offline attestation flags. Heartbeat DONE proves only this exit event. No new temperature, physical fps, optical calibration or continuous-main claim."
        hw._new_json(work / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--connection-binding", type=Path)
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--seconds", type=float, default=45.)
    parser.add_argument("--frequency", choices=("1MHz", "5MHz"), default="5MHz")
    parser.add_argument("--pds-bin", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--execute-plan", type=Path)
    args = parser.parse_args()
    if args.execute_plan:
        if args.execute:
            parser.error("--execute-plan is the explicit execution boundary")
        result = execute_plan(hw.load_json(args.execute_plan))
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result["passed"] else 1
    if any(value is None for value in (args.build_dir, args.workdir, args.connection_binding)):
        parser.error("planning requires --build-dir/--workdir/--connection-binding")
    plan = prepare_plan(args.build_dir, args.workdir, connection_binding=args.connection_binding,
                        port=args.port, seconds=args.seconds, frequency=args.frequency, pds_bin=args.pds_bin)
    print(json.dumps({"plan": str(Path(plan["workdir"]) / "plan.json"), "executing": args.execute}), flush=True)
    result = execute_plan(plan) if args.execute else plan
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if not args.execute or result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
