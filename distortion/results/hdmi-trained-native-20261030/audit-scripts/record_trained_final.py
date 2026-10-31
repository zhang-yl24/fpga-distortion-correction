"""Preserve the trained observer's new native implementation and board trial."""
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json
import sys
import zipfile

ROOT = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction")
VIS = Path(__file__).resolve().parent
BASE = ROOT / "distortion/build/hdmi-uart-diagnostic"
SOURCE = BASE / "trained-pds-1030-a"
REVIEW = BASE / "trained-review-1030-a"
BIT = BASE / "trained-bit-1030-a"
PROGRAM = ROOT / "distortion/build/offline-20261024/hdmi-trained-program-1030-a"
LIVE = ROOT / "distortion/results/hdmi-trained-live-20261030"
PACKAGE = ROOT / "distortion/results/hdmi-trained-native-20261030"
SUMMARY = ROOT / "distortion/results/hdmi-trained-20261030.json"
ARCHIVE = VIS / "hdmi-trained-20261030.zip"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def main():
    assert not PACKAGE.exists() and not SUMMARY.exists() and not ARCHIVE.exists()
    build = read(SOURCE / "build-plan.json")
    for base, entries in ((ROOT / "distortion", build["InputSHA256"]), (SOURCE, build["FrozenInputSHA256"])):
        assert all(sha((base / name).read_bytes()) == wanted for name, wanted in entries.items())
    export = read(BIT / "export-result.json")
    assert export["Passed"]
    bit = Path(export["Bitstream"]["Path"])
    assert sha(bit.read_bytes()) == export["Bitstream"]["SHA256"]
    for name, wanted in read(BIT / "export-plan.json")["InputSHA256"].items():
        assert sha(Path(name).read_bytes()) == wanted, name
    receipt = read(PROGRAM / "receipt.json")
    assert receipt["DoneConfirmed"] and receipt["Passed"] and receipt["FlashWritten"] is False
    assessment = read(LIVE / "assessment-a.json")
    assessments = {path.name:read(path) for path in LIVE.glob("assessment-*.json")}
    PACKAGE.mkdir()
    files = []
    suffixes = {".v", ".vm", ".py", ".sv", ".json", ".tcl", ".fdc", ".prt", ".log", ".rtr", ".adf", ".gnr", ".bgr", ".netlist", ".csv", ".bin", ".xml", ".pds"}

    def preserve(source, name):
        data = source.read_bytes()
        compress = len(data) > 120_000 or source.suffix in (".rtr", ".adf", ".vm", ".netlist")
        stored = gzip.compress(data, mtime=0) if compress else data
        relative = name + ".gz" if compress else name
        output = PACKAGE / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(stored)
        files.append(dict(File=relative, Source=str(source), Encoding="gzip" if compress else "identity",
                          Bytes=len(stored), SHA256=sha(stored), SourceBytes=len(data), SourceSHA256=sha(data)))

    for base, prefix in ((SOURCE, "native-build"), (REVIEW, "review"), (BIT, "bit-export"),
                         (PROGRAM, "program"), (LIVE, "live"),
                         (VIS / "trained-enable-phase-sweep-1030-a", "enable-phase-sweep"),
                         (VIS / "trained-live-static-1030-a", "live-static-review"),
                         (VIS / "trained-review-1030-a", "failed-visuals-export")):
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in suffixes and not any(x in path.parts for x in ("__pycache__", "logbackup", "xsim.dir")):
                preserve(path, prefix + "/" + path.relative_to(base).as_posix())
    for path in (VIS / "run_trained_pds.py", VIS / "run_trained_bitstream.py", VIS / "program_trained.py",
                 VIS / "trained-cpu-tests.log", VIS / "trained-cpu-tests.xml", VIS / "live-baseline-audit.json", Path(__file__),
                 ROOT / "distortion/tools/audit_hdmi_trained_native.py", ROOT / "distortion/tests/test_audit_hdmi_trained_native.py"):
        preserve(path, "audit-scripts/" + path.name)
    write(PACKAGE / "manifest.json", dict(Schema="hdmi-trained-native-evidence-manifest-v1",
        CreatedUTC=datetime.now(timezone.utc).isoformat(), Files=files, FileCount=len(files),
        StoredBytes=sum(row["Bytes"] for row in files), HardwareAccessed=True,
        Bitstream=dict(Path=str(bit), SHA256=sha(bit.read_bytes()), Bytes=bit.stat().st_size,
                       Storage="Separate local archive and original build")))
    sim = ROOT / "distortion/results/hdmi-trained-20261030"
    with zipfile.ZipFile(ARCHIVE, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for base in (sim, PACKAGE):
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(ROOT).as_posix())
        archive.write(bit, bit.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert sha(archive.read(bit.relative_to(ROOT).as_posix())) == export["Bitstream"]["SHA256"]
    write(SUMMARY, dict(Schema="hdmi-trained-progress-v1", CreatedUTC=datetime.now(timezone.utc).isoformat(),
        Target="hdmi_uart_trained_diag", NativeBuildCompleted=True, SourceDrift=[],
        ScopedADFSHA256=export["ADF_SHA256"], Bitstream=export["Bitstream"],
        SRAMProgrammed=True, DoneConfirmed=True, FlashWritten=False,
        QualifiedInputWindow=assessment["passed"], AssessmentErrors=assessment["errors"],
        QualifiedWindow=assessment.get("qualified_window"), CPUChecksPassed=225,
        InputAssessmentWindows={name:dict(Passed=row["passed"], Records=row["records"],
                                         Errors=row["errors"]) for name,row in assessments.items()},
        SimulationManifestSHA256=sha((sim / "manifest.json").read_bytes()),
        NativeManifestSHA256=sha((PACKAGE / "manifest.json").read_bytes()), NativeEvidenceFiles=len(files),
        LocalArchive=dict(Path=str(ARCHIVE), SHA256=sha(ARCHIVE.read_bytes()), Bytes=ARCHIVE.stat().st_size, Published=False),
        DDRAndDistortionVerified=False, InputPixelPayloadVerified=False, HardwareReleaseAllowed=False,
        Limits="Bound digital timing observation only. No input pixel payload, DDR/correction pipeline, external AC, physical CDC/MTBF, sustained stability or thermal acceptance."))
    for row in files:
        stored = (PACKAGE / row["File"]).read_bytes()
        raw = gzip.decompress(stored) if row["Encoding"] == "gzip" else stored
        assert sha(stored) == row["SHA256"] and sha(raw) == row["SourceSHA256"]
    print(json.dumps(dict(Passed=True, QualifiedInputWindow=assessment["passed"], Files=len(files), Summary=str(SUMMARY))))


if __name__ == "__main__":
    main()
