"""Canonical one-SGA/two-SGT capture client; importing never opens hardware.

Live execution belongs to the main board workflow. CaptureSession accepts an
injected transport/clock/sink for offline fixtures. No programming/reset or
temperature control is performed here. Host time only schedules the request.
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import time

from stats_protocol import MixedParser
from normal_function_uart import decode as decode_b4
from measurement_report import (validate_plan, validate_attestation, validate_ack,
                                validate_signature, validate_snapshot)

WINDOW_SECONDS = 20.0


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot_log_value(value):
    """Keep parser-derived arithmetic visibly provisional until report proof."""
    result = dict(value)
    result["legacy_seconds_candidate_no_wrap_unverified"] = result.pop("last_process_seconds_nominal", None)
    result["legacy_cycles_candidate_raw_plus1_no_wrap_unverified"] = result.pop("last_process_cycles_including_final_edge", None)
    result["decoded_scope"] = "Wire fields plus raw+1 candidates only; no legacy32 no-wrap or absolute-duration proof performed by collector. Use measurement_report for validated durations."
    return result


class CaptureStop(RuntimeError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


class CaptureSession:
    """Transport exposes read(n),write(bytes),flush(),close(),in_waiting.

    Sink exposes write_raw(bytes),emit(channel,dict),save(metadata). Only the
    main CLI creates disk files/serial. A byte at a time is fed to MixedParser:
    a later bad packet cannot hide an earlier complete packet in a read chunk,
    and a final complete PGSTAT can stop parsing before a partial trailing PGSIG.
    """
    def __init__(self, transport, sink, plan, manifest, attestation, *,
                 capture_kind, clock=time.monotonic):
        self.commands = validate_plan(plan)
        self.boundary = validate_attestation(manifest, attestation)
        self.transport, self.sink, self.clock = transport, sink, clock
        self.plan, self.manifest, self.attestation = plan, manifest, attestation
        self.parser = MixedParser()
        self.start = clock()
        self.raw_count = 0
        self.packet_start = self.boundary
        self.packet_wire = bytearray()
        self.state = "READY"
        self.deadline = None
        self.first_stats_time = None
        self.last_request_due = None
        self.selected_ack = None
        self.first_signature = None
        self.snapshots = []
        self.sent = []
        self.last_packet_end = None
        self.last_stats_end = None
        self.parser_consumed_end = 0
        self.meta = dict(
            capture_kind=capture_kind, outcome="NOT_STARTED", state=self.state,
            client_started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            boundary_scope="external_attested_not_proven_by_client",
            external_boundary_offset=self.boundary,
            boundary_evidence=attestation["boundary_evidence"],
            automatic_magic_resynchronization=False,
            quiet_gap_used_as_boundary_proof=False,
            explicit_reset_input_buffer_called=False,
            loaded_firmware_sha256=attestation["loaded_firmware_sha256"],
            epoch_label=attestation["epoch_label"],
            uninterrupted_reset_epoch_attested=True,
            input_description=attestation["input_description"],
            window_seconds=WINDOW_SECONDS,
            window_clock_scope="Host monotonic request scheduling only; hardware ticks/rates/epoch/wrap validation belong to measurement_report",
            host_window_guard_seconds=(1 << 32) / manifest["nominal_core_hz"],
            command_plan_scope="exact existing canonical3commands; no retries or new command identities",
            source_plan_known_limitation=plan.get("KnownLimitation"),
            selected_ack_start_offset=None, validated_analysis_start_offset=None,
            validated_analysis_end_offset=None,
            RX_packet_counts={}, startup_complete_packet_count=0,
            matching_mode1_signature_count=0, TX_requests=self.sent,
            selected_ACK=None, first_qualified_PGSIG=None, selected_snapshots=self.snapshots,
            last_cycle_sample_scope="At most2 requested last-completion endpoint samples; not a per-frame distribution",
            external_E2E="UNMEASURED", hardware_rates="NOT_COMPUTED_BY_COLLECTOR")

    def _stamp(self):
        return self.clock() - self.start

    def _event(self, name, **fields):
        self.sink.emit("events", dict(event=name, host_seconds=self._stamp(), **fields))

    def _state(self, state, timeout=None):
        self.state = state
        self.meta["state"] = state
        self.deadline = None if timeout is None else self.clock() + timeout
        self._event("STATE", state=state)

    def _send(self, index):
        if len(self.sent) != index:
            raise CaptureStop("STOPPED_TX_ORDER", "canonical command would repeat or skip")
        cmd = self.commands[index]
        wire = bytes.fromhex(cmd["Hex"])
        tx = dict(index=index + 1, magic=cmd["Magic"], ticket=cmd["Ticket"], nonce=cmd["Nonce"],
                  hex=wire.hex(), sha256=sha(wire), bytes=24,
                  rx_fence_offset=self.raw_count, host_seconds=self._stamp(),
                  disposition="WRITE_INTENT", outcome_uncertain=True)
        self.sent.append(tx)
        # Persist intention before any write. A partial/uncertain send is never retried.
        self.sink.emit("tx", dict(tx)); self.sink.save(self.metadata())
        try:
            count = self.transport.write(wire)
            tx["write_returned_bytes"] = count
            if count != len(wire):
                raise OSError("partial canonical command write")
            self.transport.flush()
        except Exception as exc:
            tx.update(disposition="WRITE_OR_DRAIN_UNCERTAIN", error=repr(exc))
            self.sink.emit("tx", dict(tx))
            raise CaptureStop("STOPPED_TX_UNCERTAIN", repr(exc)) from exc
        tx.update(disposition="HOST_WRITE_DRAINED", outcome_uncertain=False,
                  drained_host_seconds=self._stamp())
        self.sink.emit("tx", dict(tx))

    def _route(self, kind, value, start, end, packet):
        event = dict(kind=kind, start_offset=start, end_offset=end,
                     packet_sha256=sha(packet), host_seconds=self._stamp())
        counts = self.meta["RX_packet_counts"]
        counts[kind] = counts.get(kind, 0) + 1
        try:
            if self.selected_ack is None:
                if kind == "SGK1":
                    acks, frames, invalid = decode_b4(packet,
                        nonce=self.commands[0]["Nonce"], ticket=self.commands[0]["Ticket"])
                    if invalid or frames or len(acks) != 1 or not acks[0]["SchemaValid"]:
                        raise ValueError("invalid single opaque SGK1 packet")
                    event["decoded"] = acks[0]
                    if acks[0]["MatchesCommand"]:
                        ack = validate_ack(packet, self.commands[0])
                        if start < self.sent[0]["rx_fence_offset"]:
                            raise ValueError("matching ACK began before canonical SGA write")
                        self.selected_ack = dict(decoded=ack, start_offset=start,
                                                 end_offset=end, host_seconds=self._stamp())
                        self.meta.update(selected_ACK=self.selected_ack,
                            selected_ack_start_offset=start, validated_analysis_start_offset=start)
                        event["disposition"] = "MATCHED_ARMED"
                        self._state("WAIT_SIGNATURE", 15)
                    else:
                        event["disposition"] = "STARTUP_PREFIX_UNRELATED_ACK"
                else:
                    event["disposition"] = "STARTUP_PREFIX_COMPLETE_PACKET"
                if self.selected_ack is None:
                    self.meta["startup_complete_packet_count"] += 1
            elif kind == "PGSIG001":
                frame = validate_signature(packet, self.manifest, self.commands[0])
                event.update(disposition="MATCHED_MODE1_COMPLETE_PGSIG", decoded=frame)
                self.meta["matching_mode1_signature_count"] += 1
                if self.first_signature is None:
                    self.first_signature = dict(decoded=frame, start_offset=start,
                                                end_offset=end, host_seconds=self._stamp())
                    self.meta["first_qualified_PGSIG"] = self.first_signature
            elif kind == "PGSTAT02":
                if self.state not in ("WAIT_FIRST_STATS", "WAIT_LAST_STATS"):
                    raise ValueError("unsolicited, duplicate or pre-request statistics packet")
                index = 1 if self.state == "WAIT_FIRST_STATS" else 2
                validate_snapshot(value, self.manifest, self.commands[index])
                if start < self.sent[index]["rx_fence_offset"]:
                    raise ValueError("stats packet began in bytes already captured before its request")
                logged_value = snapshot_log_value(value)
                snap = dict(decoded=logged_value, start_offset=start, end_offset=end,
                            host_seconds=self._stamp(), command_index=index + 1)
                self.snapshots.append(snap)
                self.last_stats_end = end
                event.update(disposition="MATCHED_REQUESTED_PGSTAT02", decoded=logged_value)
                if index == 1:
                    self.first_stats_time = self.clock()
                    self.last_request_due = self.first_stats_time + WINDOW_SECONDS
                    self.meta["last_request_due_host_seconds"] = self.last_request_due - self.start
                    self._state("OBSERVE_WINDOW")
                else:
                    self.meta["validated_analysis_end_offset"] = end
                    self._state("COMPLETE")
            else:
                raise ValueError("unexpected packet after selected ARMED ACK: " + kind)
        except (ValueError, KeyError) as exc:
            event.update(disposition="REJECTED", error=repr(exc))
            self.sink.emit("rx", event)
            raise CaptureStop("STOPPED_PACKET_VALIDATION", repr(exc)) from exc
        self.sink.emit("rx", event)

    def ingest(self, data):
        begin = self.raw_count
        self.sink.write_raw(data)  # Always preserve the entire read BEFORE parsing.
        self.raw_count += len(data)
        for position, byte in enumerate(data, begin):
            if position < self.boundary:
                continue
            self.packet_wire.append(byte)
            self.parser_consumed_end = position + 1
            try:
                packets = self.parser.feed(bytes((byte,)))
            except ValueError as exc:
                self._event("STRICT_PARSE_ERROR", byte_offset=position, detail=str(exc))
                raise CaptureStop("STOPPED_STRICT_PARSER", str(exc)) from exc
            if packets:
                if len(packets) != 1:
                    raise CaptureStop("STOPPED_INTERNAL_PARSER_CONTRACT", "bytefeed returned multiple packets")
                kind, value = packets[0]
                packet = bytes(self.packet_wire)
                end = position + 1
                self._route(kind, value, self.packet_start, end, packet)
                self.packet_start = self.last_packet_end = end
                self.packet_wire.clear()
                if self.state == "COMPLETE":
                    # Tail of this already-saved read is retained, deliberately
                    # not fed to the parser and not mislabeled as a parse error.
                    break

    def _advance(self):
        now = self.clock()
        if self.deadline is not None and now >= self.deadline:
            raise CaptureStop("STOPPED_RESPONSE_TIMEOUT", "protocol response timeout in " + self.state)
        if self.first_stats_time is not None and self.state != "COMPLETE":
            if now - self.first_stats_time >= self.meta["host_window_guard_seconds"]:
                raise CaptureStop("STOPPED_TECHNICAL_WINDOW_GUARD", "host window exceeded one nominal uint32 core-counter interval; not a thermal limit")
        # New requests are sent AFTER consuming the current read batch. The
        # recorded raw fence also rejects an old partial matching response.
        if self.state == "WAIT_SIGNATURE" and self.first_signature is not None:
            self._state("WAIT_FIRST_STATS", 10); self._send(1)
        elif self.state == "OBSERVE_WINDOW" and now >= self.last_request_due:
            self._state("WAIT_LAST_STATS", 10); self._send(2)

    def metadata(self):
        result = dict(self.meta)
        result.update(raw_bytes=self.raw_count, parser_consumed_end_offset=self.parser_consumed_end,
            last_fully_parsed_packet_end_offset=self.last_packet_end,
            last_validated_stats_end_offset=self.last_stats_end,
            known_boundary_reached=self.raw_count >= self.boundary,
            requests_attempted=len(self.sent), responses_selected=len(self.snapshots),
            elapsed_host_seconds=self._stamp(), parser_buffer_bytes=len(self.parser.buffer))
        return result

    def run(self):
        try:
            self.meta["outcome"] = "IN_PROGRESS"
            self._state("WAIT_ARMED_ACK", 15); self._send(0)
            while self.state != "COMPLETE":
                self._advance()
                data = self.transport.read(max(1, min(4096, self.transport.in_waiting)))
                if data:
                    self.ingest(data)
                self._advance()
            self.parser.finish()  # Only the validated prefix has been fed.
            self.meta["outcome"] = "CAPTURE_COMPLETE_TWO_SNAPSHOTS"
        except CaptureStop as exc:
            self.meta.update(outcome=exc.code, error=str(exc))
            self._state("STOPPED")
        except (Exception, KeyboardInterrupt) as exc:
            self.meta.update(outcome="STOPPED_TRANSPORT_OR_INTERRUPT", error=repr(exc))
            self._state("STOPPED")
        finally:
            try:
                self.transport.close()
                self.meta["port_close_returned"] = True
            except Exception as exc:
                self.meta["port_close_error"] = repr(exc)
            self.meta["client_finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
            self.sink.save(self.metadata())
        return self.metadata()


class CaptureFiles:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=False)
        self.raw = (self.root / "uart.raw.bin").open("xb", buffering=0)
        self.logs = {name: (self.root / (name + ".jsonl")).open("x", encoding="utf-8", buffering=1)
                     for name in ("rx", "tx", "events")}

    def write_raw(self, data):
        if self.raw.write(data) != len(data):
            raise OSError("short raw capture file write")

    def emit(self, channel, value):
        self.logs[channel].write(json.dumps(value, ensure_ascii=False) + "\n")
        self.logs[channel].flush()

    def save(self, meta):
        pending = self.root / "capturemeta.json.tmp"
        pending.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pending.replace(self.root / "capturemeta.json")

    def finalize(self, meta):
        self.raw.close()
        for handle in self.logs.values():
            handle.close()
        wire = (self.root / "uart.raw.bin").read_bytes()
        external_offset = min(meta["external_boundary_offset"], len(wire))
        selected = meta.get("selected_ack_start_offset")
        offset = min(selected if isinstance(selected, int) else meta["external_boundary_offset"], len(wire))
        prefix = wire[:offset]
        (self.root / "startup_prefix.bin").write_bytes(prefix)
        end = meta.get("validated_analysis_end_offset")
        tail = wire[end:] if isinstance(end, int) else b""
        if isinstance(end, int):
            (self.root / "retained_tail.bin").write_bytes(tail)
        meta.update(raw_sha256=sha(wire), raw_bytes=len(wire),
            raw_file="uart.raw.bin", startup_prefix_bytes=len(prefix), startup_prefix_sha256=sha(prefix),
            external_unparsed_prefix_bytes=external_offset,
            external_unparsed_prefix_sha256=sha(wire[:external_offset]),
            startup_prefix_scope="All bytes before selected ACK, including externally skipped prefix and strictly parsed old complete packets" if isinstance(selected, int) else "Captured bytes before the externally supplied boundary; no selected ACK",
            retained_tail_bytes=len(tail) if isinstance(end, int) else None,
            retained_tail_sha256=sha(tail) if isinstance(end, int) else None,
            tail_scope="Retained unparsed bytes after final selected PGSTAT, not an end-of-stream parse error" if isinstance(end, int) else "No complete final analysis boundary; raw capture remains preserved")
        self.save(meta)
        return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "manifest", "run-attestation", "output-dir"):
        ap.add_argument("--" + name, type=Path, required=True)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, choices=(115200,), default=115200)
    args = ap.parse_args()
    # Parse and hash the SAME immutable read of each input, including any BOM.
    input_file_bytes = {
        "plan": args.plan.read_bytes(),
        "manifest": args.manifest.read_bytes(),
        "run_attestation": args.run_attestation.read_bytes(),
    }
    inputs = {name: json.loads(data.decode("utf-8-sig")) for name, data in input_file_bytes.items()}
    plan, manifest, attestation = inputs["plan"], inputs["manifest"], inputs["run_attestation"]
    validate_plan(plan); validate_attestation(manifest, attestation)
    if not args.port.strip():
        ap.error("--port must name the main workflow's verified serial port")
    files = CaptureFiles(args.output_dir)
    session = CaptureSession(None, files, plan, manifest, attestation, capture_kind="LIVE_SERIAL_CAPTURE")
    session.meta.update(plan_sha256=sha(input_file_bytes["plan"]), manifest_sha256=sha(input_file_bytes["manifest"]),
        run_attestation_sha256=sha(input_file_bytes["run_attestation"]),
        serial=dict(port=args.port, baud=args.baud, bytesize=8, parity="N", stopbits=1,
                    DTR=False, RTS=False, xonxoff=False, rtscts=False, dsrdtr=False))
    port = None
    try:
        import serial  # Deliberately deferred; import/help/offline fixtures never open COM.
        port = serial.Serial(port=None, baudrate=args.baud, bytesize=8, parity="N", stopbits=1,
            timeout=.1, write_timeout=2, xonxoff=False, rtscts=False, dsrdtr=False)
        port.dtr = False; port.rts = False; port.port = args.port
        session.transport = port
        files.save(session.metadata())
        port.open()
        session.meta["serial_open_returned"] = True
        meta = session.run()
    except (Exception, KeyboardInterrupt) as exc:
        session.meta.update(outcome="STOPPED_SETUP_OR_OPEN", error=repr(exc))
        meta = session.metadata()
    finally:
        # A second close/flag query must never bypass raw hashing/finalization.
        # Capture completeness and transport cleanup are separate outcomes.
        if port is not None:
            try:
                if port.is_open:
                    port.close()
                closed = not port.is_open
                session.meta.update(port_closed_confirmed=closed,
                    cleanup_status="PORT_CLOSED_CONFIRMED" if closed else "PORT_CLOSE_UNCONFIRMED")
            except (Exception, KeyboardInterrupt) as exc:
                session.meta.update(port_close_error=repr(exc), port_closed_confirmed=False,
                                    cleanup_status="PORT_CLOSE_UNCONFIRMED")
        else:
            session.meta.update(port_closed_confirmed=True, cleanup_status="PORT_NOT_CREATED")
        meta = session.metadata()
    meta = files.finalize(meta)
    print(json.dumps(dict(outcome=meta["outcome"], raw_bytes=meta["raw_bytes"],
        raw_sha256=meta["raw_sha256"], selected_ack_start_offset=meta["selected_ack_start_offset"],
        validated_analysis_end_offset=meta["validated_analysis_end_offset"],
        cleanup_status=meta["cleanup_status"], port_closed_confirmed=meta["port_closed_confirmed"]), indent=2))
    return 0 if meta["outcome"] == "CAPTURE_COMPLETE_TWO_SNAPSHOTS" and meta["port_closed_confirmed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
