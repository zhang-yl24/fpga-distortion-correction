"""Preserve an independently verified offline export; never access hardware."""
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json
import sys
import zipfile

ROOT = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion")
sys.path.insert(0, str(ROOT / "tools"))
import verify_hdmi_input_bitstream as verification

WORK = ROOT / "build/hdmi-uart-diagnostic/input-bit-1030-a"
DIRECT = ROOT / "build/hdmi-uart-diagnostic/input-bit-final-export-1030-a"
PLAN = ROOT / "build/offline-20261024/hdmi-input-program-1030-b"
PACKAGE = ROOT / "results/hdmi-input-bitstream-20261030"
SUMMARY = ROOT / "results/hdmi-input-bitstream-20261030.json"
ARCHIVE = Path(__file__).parent / "hdmi-input-bitstream-20261030.zip"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def main():
    assert not PACKAGE.exists() and not SUMMARY.exists() and not ARCHIVE.exists()
    checked = verification.verify(WORK)
    assert checked["Passed"] and not checked["HardwareAccessed"]
    direct = json.loads((DIRECT / "review.json").read_text(encoding="utf-8"))
    assert direct["AuditPassed"] and direct["SourceADFSHA256"] == verification.prepare.ADF_SHA256
    assert direct["All46PinsAndDirectionsMatch"] and direct["VerifiedSynchronizerFFCount"] == 161
    assert direct["VerifiedStageLinkCount"] == 81 and direct["EntireParsedFunctionalGraphUnchanged"]
    for name, wanted in direct["EvidenceSHA256"].items():
        assert digest(Path(name).read_bytes()) == wanted, name
    native = json.loads((DIRECT / "execution.json").read_text(encoding="utf-8"))
    assert native["ReturnCode"] == 0 and native["HardwareAccessed"] is False
    assert native["OriginalADFUnchanged"] and native["CopiedADFUnchanged"] and not native["InputDrift"]
    for name, wanted in native["OutputSHA256"].items():
        assert digest((DIRECT / name).read_bytes()) == wanted, name
    plan = json.loads((PLAN / "plan.json").read_text(encoding="utf-8"))
    assert plan["Bitstream"]["SHA256"] == verification.BIT_SHA256
    assert plan["Executed"] is False and plan["HardwareAccessed"] is False
    for name, wanted in plan["BoundInputSHA256"].items():
        assert digest(Path(name).read_bytes()) == wanted, name
    PACKAGE.mkdir()
    files = []

    def preserve(source, name):
        raw = source.read_bytes()
        compressed = source.suffix in (".rtr", ".vm", ".adf") or (source.suffix == ".v" and len(raw) > 1_000_000)
        data = gzip.compress(raw, mtime=0) if compressed else raw
        name = name + ".gz" if compressed else name
        destination = PACKAGE / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(data)
        origin = source.relative_to(ROOT.parent).as_posix() if source.is_relative_to(ROOT.parent) else str(source)
        files.append(dict(File=name, Source=origin, SHA256=digest(data), Bytes=len(data),
                          SourceSHA256=digest(raw), SourceBytes=len(raw), Encoding="gzip" if compressed else "identity"))

    names = ["bitstream-plan.json", "pre-bit-audit.json", "export-result.json", "export.tcl",
             "native-stdout.log", "native-stderr.log", "run.log", "hdmi_uart_input_diag.pds",
             "generate_bitstream/hdmi_uart_input_diag.bgr", "generate_bitstream/run.log",
             "report_timing/hdmi_uart_input_diag.rtr", "report_timing/hdmi_uart_input_diag_exception.rtr"]
    for name in names:
        preserve(WORK / name, "export/" + name)
    checked_path = Path(__file__).parent / "verification.json"
    write_json(checked_path, checked)
    preserve(checked_path, "verification.json")
    for source in sorted(DIRECT.rglob("*")):
        if source.is_file() and source.suffix not in (".db", ".pyc") and "__pycache__" not in source.parts:
            preserve(source, "final-adf-export/" + source.relative_to(DIRECT).as_posix())
    for name in ("plan.json", "scan.tcl", "program.tcl"):
        preserve(PLAN / name, "download-plan/" + name)
    for name in ("prepare_hdmi_input_bitstream", "assess_hdmi_input", "verify_hdmi_input_bitstream", "prepare_hdmi_input_program"):
        preserve(ROOT / "tools" / (name + ".py"), "tools/" + name + ".py")
        preserve(ROOT / "tests" / ("test_" + name + ".py"), "tests/test_" + name + ".py")
    preserve(Path(__file__), "record.py")
    for name in ("cpu-tests.log", "cpu-tests.xml", "baseline-audit.json", "old-control-assessment.json"):
        preserve(Path(__file__).parent / name, "validation/" + name)
    bit = WORK / verification.BITSTREAM
    write_json(PACKAGE / "manifest.json", dict(Schema="hdmi-input-bitstream-evidence-manifest-v1",
        CreatedUTC=datetime.now(timezone.utc).isoformat(), Files=files,
        Bitstream=dict(Path=bit.relative_to(ROOT.parent).as_posix(), SHA256=verification.BIT_SHA256,
                       Bytes=bit.stat().st_size, Storage="Local build and separate offline archive"),
        PriorEvidenceManifest=dict(Path=verification.prepare.EVIDENCE + "/manifest.json", SHA256=verification.prepare.MANIFEST_SHA256),
        HardwareAccessed=False, HardwareReleaseAllowed=False))
    with zipfile.ZipFile(ARCHIVE, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(PACKAGE.rglob("*")):
            if source.is_file():
                archive.write(source, source.relative_to(ROOT.parent).as_posix())
        for source in sorted(WORK.rglob("*")):
            if source.is_file() and source.suffix not in (".db", ".pyc", ".smsk") and "__pycache__" not in source.parts:
                archive.write(source, source.relative_to(ROOT.parent).as_posix())
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert digest(archive.read(bit.relative_to(ROOT.parent).as_posix())) == verification.BIT_SHA256
    write_json(SUMMARY, dict(Schema="hdmi-input-bitstream-progress-v1", RecordedUTC=datetime.now(timezone.utc).isoformat(),
        Target=verification.prepare.TARGET, OfflineBitstreamGenerated=True, OfflineVerificationPassed=True,
        FinalADFSHA256=verification.prepare.ADF_SHA256, Bitstream=checked["Bitstream"], NativeAudit=checked["NativeAudit"],
        OriginalExecutionReceiptPassed=False, OriginalExecutionReceiptPreserved=True,
        StageClassifierFailureReconciled=True, FreshSynthesisOrPNRInThisExport=False,
        ExactFinalADFGraphAndPlacementUnchanged=True, ExactFinalADFIOPinsVerified=46,
        ExactFinalADFSynchronizerFFVerified=161, ExactFinalADFStageLinksVerified=81,
        ExactFinalADFReviewSHA256=digest((DIRECT / "review.json").read_bytes()),
        CPUChecks=dict(Passed=179, Failed=0), BaselineAuditsPassed=4,
        BoardPowerState="User reported board powered off in current chat", HardwareAccessedThisRound=False,
        ObserverProgrammed=False, FlashWritten=False, InputGeometryMeasuredOnBoard=False,
        DDRAndDistortionVerified=False, ThermalStatusResolved=False, HardwareReleaseAllowed=False,
        EvidenceManifest=dict(Path=PACKAGE.relative_to(ROOT.parent).as_posix() + "/manifest.json",
            SHA256=digest((PACKAGE / "manifest.json").read_bytes()), FileCount=len(files), StoredBytes=sum(row["Bytes"] for row in files)),
        LocalArchive=dict(Path=str(ARCHIVE), SHA256=digest(ARCHIVE.read_bytes()), Bytes=ARCHIVE.stat().st_size, Published=False),
        Limits=["Digital timing observer only; no input pixel payload, DDR, distortion, physical CDC/AC, temperature or stability acceptance.",
                "Original failed wrapper receipt retained; separate verification checks actual PDS process events and frozen bytes.",
                "Board remains powered off; scan/program Tcl have not been executed."]))
    assert verification.verify(WORK)["Passed"]
    print(json.dumps(dict(Passed=True, Files=len(files), Summary=str(SUMMARY), Archive=str(ARCHIVE))))


if __name__ == "__main__":
    main()
