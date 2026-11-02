"""Bounded receive-only statistics capture; never program or transmit UART data.

Default COM7/115200 matches the isolated statistics candidate, not the 921600
raw-image firmware. Expected IDs are labels, not proof of the loaded bitstream.
Importing this module does not import pyserial or open any device.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time

import camera720_stats as decoder_module

SELF = Path(__file__).resolve()
DECODER = SELF.with_name("camera720_stats.py")
DECODER_SHA = "f47dd50df0f0a9fc389556e84f56ea1b9041ee98e8637ab253255983a22708cb"
DEFAULT_PORT, DEFAULT_BAUD = "COM7", 115200
DEFAULT_SECONDS, DEFAULT_MAX_BYTES = 30.0, 1048576


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n"


def validate(expected_build_id, expected_profile_id, seconds, max_bytes, nominal_core_hz):
    for name, value in (("build", expected_build_id), ("profile", expected_profile_id)):
        require(isinstance(value, str) and re.fullmatch("[0-9a-f]{16}", value)
                and int(value, 16) != 0, f"expected {name} ID must be an explicit nonzero 16-digit lowercase hex label")
    require(type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 300,
            "receive duration must be finite and in (0,300] seconds")
    require(type(max_bytes) is int and 64 <= max_bytes <= 4194304,
            "byte limit must be an integer in [64,4194304]")
    decoder_module.validate_frequency(nominal_core_hz)
    require(Path(decoder_module.__file__).resolve() == DECODER and sha(DECODER) == DECODER_SHA,
            "frozen statistics decoder is missing or changed")


def open_serial(port_name, baud):
    """Only the explicitly invoked live receiver reaches this lazy import."""
    import serial
    port = serial.Serial(port=None, baudrate=baud, timeout=.25, write_timeout=0,
                         dsrdtr=False, rtscts=False, xonxoff=False)
    try:
        port.dtr, port.rts, port.port = False, False, port_name
        port.open()
        return port
    except BaseException as error:
        try:
            port.close()
        except Exception as close_error:
            raise RuntimeError(f"serial open failed: {type(error).__name__}: {error}; "
                               f"close also failed: {type(close_error).__name__}: {close_error}") from error
        raise


def receive_stream(stream_factory, output, *, expected_build_id, expected_profile_id,
                   seconds=DEFAULT_SECONDS, max_bytes=DEFAULT_MAX_BYTES,
                   nominal_core_hz=125000000, clock=time.monotonic,
                   source_kind="injected_test_stream", serial_configuration=None):
    """Consume a supplied open read-only stream; tests inject mocks here.

    Stream must expose read(n), in_waiting, timeout and close(). No write, flush,
    reset_input_buffer or other UART command is ever called. Real receive uses a
    serial factory only after validation and fresh output creation succeed.
    """
    validate(expected_build_id, expected_profile_id, seconds, max_bytes, nominal_core_hz)
    require(source_kind in ("injected_test_stream", "serial_receive"), "explicit source kind required")
    output = Path(output).resolve()
    require(output.parent.is_dir() and not output.exists(), "fresh session directory under an existing parent required")
    watched = {str(SELF): sha(SELF), str(DECODER): DECODER_SHA}
    output.mkdir()
    decoder, stream = decoder_module.StreamDecoder(), None
    report = {
        "Schema": "camera720-core-stats-receive-v1", "StartedUTC": datetime.now(timezone.utc).isoformat(),
        "SourceKind": source_kind, "SerialConfiguration": serial_configuration,
        "ExpectedBuildID": expected_build_id, "ExpectedProfileID": expected_profile_id,
        "MaximumSeconds": seconds, "MaximumBytes": max_bytes, "NominalCoreHz": nominal_core_hz,
        "ReceptionCompletedWithoutError": False, "ReceptionAndIdentityPassed": False,
        "StreamOpened": False, "HardwareAccessAttempted": False, "HardwareAccessed": False,
        "UARTTransmitBytes": 0, "JTAGAccessed": False, "FPGAProgrammed": False,
        "FPGAImageCryptographicallyVerified": False, "IdentityLabelsAuthenticateHardware": False,
        "ResetEpochContinuityProven": False, "AssumesContinuousResetEpoch": True,
        "IndependentCoreFrequencyMeasured": False, "SensorInputFPSMeasured": False,
        "HDMIRefreshFPSMeasured": False, "UnderflowsAvailable": False, "Underflows": None,
        "FaultFreeProven": False, "FaultStatusAvailableForAllWindows": False,
        "KnownFaultObserved": None, "InputSHA256": watched,
        "Limits": "Expected 64-bit IDs are checked, but require an external full source/bit/program binding. "
                  "Core FPS uses nominal clock frequency and assumes an uninterrupted reset epoch; "
                  "unobserved resets cannot always be identified. Host read completion times include "
                  "USB/OS buffering and are not snapshot or exposure timestamps. Reception success "
                  "does not mean fault-free hardware, optical acceptance, or zero underflows."
    }
    totals = {"SourceAccepted": 0, "Processed": 0, "UniquePresented": 0}
    packet_count = mismatch_count = window_count = valid_windows = byte_count = read_count = 0
    selected_ticks = 0
    all_status_known, fault_observed = True, False
    previous, started = None, None
    try:
        with (output / "received-wire.bin").open("xb") as raw, \
                (output / "reads.jsonl").open("x", encoding="utf-8", newline="\n") as reads, \
                (output / "packets.jsonl").open("x", encoding="utf-8", newline="\n") as packets, \
                (output / "windows.jsonl").open("x", encoding="utf-8", newline="\n") as windows:
            report["HardwareAccessAttempted"] = source_kind == "serial_receive"
            stream = stream_factory()
            report["StreamOpened"] = True
            report["HardwareAccessed"] = source_kind == "serial_receive"
            started = clock()
            deadline = started + seconds
            while byte_count < max_bytes:
                before = clock()
                if before >= deadline:
                    report["EndReason"] = "duration_limit"
                    break
                stream.timeout = min(.25, deadline - before)
                requested = min(4096, max_bytes - byte_count, max(1, stream.in_waiting))
                data = stream.read(requested)
                after = clock()
                require(isinstance(data, (bytes, bytearray)) and len(data) <= requested,
                        "stream returned invalid bytes or exceeded requested length")
                raw.write(data)
                reads.write(encode({"ReadIndex": read_count, "StartSeconds": before - started,
                    "CompletedSeconds": after - started, "RequestedBytes": requested,
                    "WireStart": byte_count, "WireEnd": byte_count + len(data)}))
                # Per-byte feed locates each CRC-valid packet exactly, including
                # protocol rejection/noise between two records in the same read.
                for byte in data:
                    byte_count += 1
                    for value in decoder.feed(bytes((byte,))):
                        matches = (value["BuildID"] == expected_build_id
                                   and value["ProfileID"] == expected_profile_id)
                        item = {"PacketIndex": packet_count, "WireStart": byte_count - 64,
                            "WireEnd": byte_count, "DecodedInReadIndex": read_count,
                            "CompletingReadStartedSeconds": before - started,
                            "CompletingReadEndedSeconds": after - started,
                            "HostTimeIsSnapshotTime": False, "ExpectedIDsMatch": matches,
                            "RejectedPacketsBefore": decoder.rejected_packets,
                            "DiscardedBytesBefore": decoder.discarded_bytes, "Packet": value}
                        packets.write(encode(item))
                        mismatch_count += not matches
                        packet_count += 1
                        if previous is not None:
                            window_count += 1
                            reason = None
                            if not matches or not previous["ExpectedIDsMatch"]:
                                reason = "expected_identity_mismatch"
                            elif (item["RejectedPacketsBefore"] != previous["RejectedPacketsBefore"]
                                  or item["DiscardedBytesBefore"] != previous["DiscardedBytesBefore"]):
                                reason = "corrupt_or_unframed_bytes_between_packets"
                            rates = (decoder_module.rate_between(previous["Packet"], value, nominal_core_hz)
                                     if reason is None else {"RatesAvailable": False, "Reason": reason})
                            host_delta = after - started - previous["CompletingReadEndedSeconds"]
                            comparison = {"ReadCompletionDeltaSeconds": host_delta,
                                "TimingIncludesUSBAndOSBuffering": True,
                                "HostTimesAreSnapshotTimes": False,
                                "HostToNominalDurationRatio": (host_delta / rates["NominalSeconds"]
                                    if rates["RatesAvailable"] and host_delta > 0 else None)}
                            windows.write(encode({"WindowIndex": window_count - 1,
                                "PreviousPacketIndex": previous["PacketIndex"], "CurrentPacketIndex": item["PacketIndex"],
                                "ValidCounterWindow": rates["RatesAvailable"], "Rates": rates,
                                "HostTiming": comparison, "ResetEpochContinuityProven": False,
                                "AssumesContinuousResetEpoch": True}))
                            if rates["RatesAvailable"]:
                                valid_windows += 1
                                selected_ticks += rates["CoreTickDelta"]
                                for name in totals:
                                    totals[name] += rates["FrameDeltas"][name]
                                all_status_known &= rates["StatusKnownAtBothSamples"]
                                fault_observed |= rates["FaultObserved"]
                        previous = item
                read_count += 1
            else:
                report["EndReason"] = "byte_limit"
        report["ReceptionCompletedWithoutError"] = True
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__ + ": " + str(error)
        report["EndReason"] = "error_or_interruption"
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception as error:
                report["CloseError"] = type(error).__name__ + ": " + str(error)
                report["ReceptionCompletedWithoutError"] = False
        report["ElapsedSecondsAfterOpen"] = clock() - started if started is not None else None
        report["FinishedUTC"] = datetime.now(timezone.utc).isoformat()
        report["SourceDrift"] = [p for p, h in watched.items() if not Path(p).is_file() or sha(p) != h]
        received_bytes = (output / "received-wire.bin").stat().st_size if (output / "received-wire.bin").is_file() else 0
        report.update(BytesReceived=received_bytes, BytesExaminedByDecoder=byte_count,
            NoDataReceived=received_bytes == 0, ReadCalls=read_count, CompletePackets=packet_count,
            MatchingPackets=packet_count - mismatch_count,
            IdentityMismatches=mismatch_count, RejectedPackets=decoder.rejected_packets,
            DiscardedBytes=decoder.discarded_bytes, TrailingPartialBytes=len(decoder.pending),
            CounterWindows=window_count, ValidCounterWindows=valid_windows,
            ExcludedCounterWindows=window_count - valid_windows)
        report["ReceptionAndIdentityPassed"] = bool(report["ReceptionCompletedWithoutError"] and valid_windows
            and not mismatch_count and not decoder.rejected_packets and not report["SourceDrift"])
        report["FaultStatusAvailableForAllWindows"] = bool(valid_windows and all_status_known)
        report["KnownFaultObserved"] = True if fault_observed else (False if valid_windows and all_status_known else None)
        duration = selected_ticks / nominal_core_hz
        if not math.isfinite(duration):
            report["AggregateNumericError"] = "selected nominal duration exceeds finite numeric range"
            report["ReceptionAndIdentityPassed"] = False
            duration = None
        report["SelectedWindows"] = {"Count": valid_windows, "CoreTicks": selected_ticks,
            "NominalSeconds": duration, "FrameDeltas": totals,
            "SourceAcceptedFPS": totals["SourceAccepted"] / duration if duration else None,
            "ProcessedFPS": totals["Processed"] / duration if duration else None,
            "UniquePresentedFPS": totals["UniquePresented"] / duration if duration else None,
            "IsWholeHostSessionAverage": False, "AssumesContinuousResetEpochWithinEachWindow": True}
        report["Artifacts"] = {p.name: {"Path": str(p), "SHA256": sha(p), "Bytes": p.stat().st_size}
                               for p in output.iterdir() if p.is_file()}
        with (output / "session.json").open("x", encoding="utf-8", newline="\n") as result:
            result.write(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    return report


def receive(output, *, expected_build_id, expected_profile_id, port=DEFAULT_PORT, baud=DEFAULT_BAUD,
            seconds=DEFAULT_SECONDS, max_bytes=DEFAULT_MAX_BYTES, nominal_core_hz=125000000):
    require(isinstance(port, str) and re.fullmatch(r"COM[1-9][0-9]*", port), "explicit Windows COM port required")
    require(type(baud) is int and 1200 <= baud <= 2000000, "baud must be an integer in [1200,2000000]")
    return receive_stream(lambda: open_serial(port, baud), output, expected_build_id=expected_build_id,
        expected_profile_id=expected_profile_id, seconds=seconds, max_bytes=max_bytes,
        nominal_core_hz=nominal_core_hz, source_kind="serial_receive",
        serial_configuration={"Port": port, "Baud": baud, "DataBits": 8, "Parity": "N", "StopBits": 1,
                              "DTR": False, "RTS": False, "FlowControl": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-build-id", required=True)
    parser.add_argument("--expected-profile-id", required=True)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--nominal-core-hz", type=float, default=125000000)
    args = parser.parse_args()
    value = receive(args.output, expected_build_id=args.expected_build_id,
        expected_profile_id=args.expected_profile_id, port=args.port, baud=args.baud,
        seconds=args.seconds, max_bytes=args.max_bytes, nominal_core_hz=args.nominal_core_hz)
    print(json.dumps({k: value[k] for k in ("ReceptionAndIdentityPassed", "CompletePackets",
        "IdentityMismatches", "RejectedPackets", "ValidCounterWindows", "HardwareAccessed")}))
    return 0 if value["ReceptionAndIdentityPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
