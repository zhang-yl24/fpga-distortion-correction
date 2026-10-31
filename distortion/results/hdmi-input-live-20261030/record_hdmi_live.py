"""Record this observer programming event and preserve failed input evidence."""
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import hashlib
import json
import shutil
import struct
import sys
import zlib

ROOT = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction")
VIS = Path(__file__).resolve().parent
PACKAGE = ROOT / "distortion/results/hdmi-input-live-20261030"
PROGRAM = ROOT / "distortion/build/offline-20261024/hdmi-input-program-1030-b"
SUMMARY = ROOT / "distortion/results/hdmi-input-live-20261030.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, result):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def independent(wire, receipt):
    raw = wire.read_bytes()
    reported = json.loads(receipt.read_text(encoding="utf-8"))
    assert len(raw) % 64 == 0
    rows = []
    for start in range(0, len(raw), 64):
        p = raw[start:start + 64]
        assert p[:8] == b"PGHDMI01" and p[60:] == b"HM01"
        assert zlib.crc32(p[:56]) == struct.unpack_from("<I", p, 56)[0]
        seq, ticks = struct.unpack_from("<II", p, 8)
        flags = struct.unpack_from("<H", p, 16)[0]
        width, height = struct.unpack_from("<HH", p, 20)
        edges, good, bad, age, transactions = struct.unpack_from("<IIIII", p, 24)
        rows.append(dict(sequence=seq, ticks=ticks, flags=flags, cfg_error=p[18], fault=p[19],
                         width=width, height=height, edges=edges, good=good, bad=bad,
                         cfg_age=age, transactions=transactions))
    for previous, current in zip(rows, rows[1:]):
        assert (current["sequence"] - previous["sequence"]) & 0xffffffff == 1
        assert (current["ticks"] - previous["ticks"]) & 0xffffffff == 13_500_000
    assert reported["accepted_packets"] == len(rows) and reported["wire_sha256"] == sha(wire)
    for actual, decoded in zip(rows, reported["frames"]):
        for a, b in (("sequence", "sequence"), ("ticks", "reference_ticks"), ("flags", "flags"),
                     ("fault", "input_fault"), ("width", "width"), ("height", "height"),
                     ("edges", "pclk_edges"), ("good", "good_frames"), ("bad", "bad_frames"),
                     ("transactions", "completed_transactions")):
            assert actual[a] == decoded[b]
    return dict(Passed=True, Scope="Independent struct/zlib wire reparse, not video acceptance",
                Packets=len(rows), First=rows[0], Last=rows[-1], Flags=dict(Counter(hex(r["flags"]) for r in rows)),
                ReferenceSpanSeconds=(len(rows)-1) * 0.5,
                GoodFramesAdvanced=rows[-1]["good"]-rows[0]["good"],
                BadFramesAdvanced=rows[-1]["bad"]-rows[0]["bad"],
                PixelClockEdgesRange=[min(r["edges"] for r in rows), max(r["edges"] for r in rows)],
                WireSHA256=sha(wire), ReceiptSHA256=sha(receipt))


def main():
    assert not SUMMARY.exists()
    program = json.loads((PROGRAM / "receipt.json").read_text(encoding="utf-8"))
    assert program["Passed"] and program["DoneConfirmed"] and not program["FlashWritten"]
    for name, wanted in program["Logs"].items():
        assert sha(PROGRAM / name) == wanted
    target = PACKAGE / "program"
    target.mkdir()
    for source in sorted(PROGRAM.iterdir()):
        if source.is_file():
            shutil.copyfile(source, target / source.name)
            assert sha(source) == sha(target / source.name)
    result = {}
    for key, name in (("BeforeReplugA", "live-status-a"), ("BeforeReplugB", "live-status-b"),
                      ("AfterReplugC", "live-status-c-after-replug")):
        result[key] = independent(PACKAGE / (name + ".raw.bin"), PACKAGE / (name + ".json"))
    save(PACKAGE / "independent-uart-check.json", result)
    save(PACKAGE / "user-observations.json", dict(BoardPoweredOn=True, InputHDMICableReplugged=True,
         DisplayShowsEightColorBars=True, Source="Explicit user replies during this programming session",
         PhotoTakenByThisRound=False, Limits="User observation only; bars are FPGA generated, no input pixels or corrected image."))
    for source in (ROOT / "distortion/tools/execute_hdmi_input_program.py",
                   ROOT / "distortion/tests/test_execute_hdmi_input_program.py",
                   VIS / "live-cpu-tests.log", VIS / "live-cpu-tests.xml", Path(__file__)):
        shutil.copyfile(source, PACKAGE / source.name)
    # Keep full Windows snapshots local; only HDMI target extracts enter evidence.
    windows = VIS / "live-windows-originals"
    windows.mkdir()
    for source in PACKAGE.glob("windows-display-*.json"):
        if not source.name.endswith("-hdmi-only.json"):
            wanted = sha(source)
            shutil.move(str(source), str(windows / source.name))
            assert sha(windows / source.name) == wanted
    files = [dict(File=p.relative_to(PACKAGE).as_posix(), SHA256=sha(p), Bytes=p.stat().st_size)
             for p in sorted(PACKAGE.rglob("*")) if p.is_file()]
    save(PACKAGE / "manifest.json", dict(Schema="hdmi-input-live-evidence-v1", Files=files,
         RecordedUTC=datetime.now(timezone.utc).isoformat(), RawEvidenceUnmodified=True,
         OriginalWindowsSnapshotsLocalOnly=str(windows), HardwareAccessed=True))
    c = result["AfterReplugC"]
    save(SUMMARY, dict(Schema="hdmi-input-live-progress-v1", RecordedUTC=datetime.now(timezone.utc).isoformat(),
         Target=program["Target"], BitstreamSHA256=program["Bitstream"]["SHA256"],
         SRAMProgrammed=True, DoneConfirmed=True, FlashWritten=False,
         ProgrammingStartUTC=program["StartedUTC"], ProgrammingEndUTC=program["EndedUTC"],
         Device="PG2L100H", DeviceID="0x00602899", ScanDoneBefore=0, ScanDoneAfter=1,
         UARTPackets=50, UARTCRCRejected=0, AllConfigurationErrorsZero=True,
         BeforeReplugRXInitCompleted=False, AfterReplugRXAndAllInitCompleted=True,
         AfterReplugObserverReleased=True, InputObservationPassed=False, QualifiedInputWindow=False,
         FaultCode="0x15", FaultMeaning="DE asserted during normalized VS active interval",
         PixelClockMHzRange=[n/1000 for n in c["PixelClockEdgesRange"]],
         WidthReported=0, HeightReported=1080, GoodFramesAdvanced=0,
         BadFrameBoundariesAdvanced=c["BadFramesAdvanced"], ReferenceSpanSeconds=c["ReferenceSpanSeconds"],
         UserReportedColorBars=True, InputPixelPayloadVerified=False, DDRAndDistortionVerified=False,
         HardwareReleaseAllowed=False, TemperatureStatusResolved=False, StatusWord="0x081ffca0",
         CPUChecksPassed=203, EvidenceManifestSHA256=sha(PACKAGE / "manifest.json"),
         Limits=["Clock/geometry telemetry only; this attempt did not qualify input timing and has no pixel payload.",
                 "First-ready edge gate and first-DE polarity vulnerability reproduced in separate digital simulations; physical transient cause remains an inference.",
                 "Bad-frame absolute total includes startup abnormal boundaries; only +285 over the recorded 9.5s is interpreted here.",
                 "Current board still runs this observer diagnostic; TX bars are synthetic, no DDR/rectification chain."]))
    print(json.dumps(dict(Passed=True, Files=len(files), Summary=str(SUMMARY), InputObservationPassed=False)))


if __name__ == "__main__":
    main()
