"""Seal existing native simulation evidence; never run EDA or hardware."""
from pathlib import Path
from datetime import datetime, timezone
import gzip
import hashlib
import json

REPO = Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction")
PROJECT = REPO / "distortion"
VIS = Path(__file__).resolve().parent
OUT = PROJECT / "results/hdmi-trained-20261030"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def dump(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


assert not OUT.exists(), "new evidence package required"
OUT.mkdir()
files = []


def store(source, relative, note=None):
    source = Path(source).resolve()
    raw = source.read_bytes()
    target = OUT / relative
    encoding = "gzip" if len(raw) >= 65_536 and source.suffix in (".log", ".csv") else "identity"
    if encoding == "gzip":
        target = target.with_name(target.name + ".gz")
        data = gzip.compress(raw, compresslevel=9, mtime=0)
    else:
        data = raw
    assert target.resolve().is_relative_to(OUT.resolve()) and not target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)
    entry = dict(File=target.relative_to(OUT).as_posix(), Bytes=len(data), SHA256=digest(data),
                 Source=str(source), SourceBytes=len(raw), SourceSHA256=digest(raw), Encoding=encoding)
    if note:
        entry["Note"] = note
    files.append(entry)
    assert (gzip.decompress(target.read_bytes()) if encoding == "gzip" else target.read_bytes()) == raw


allowed = {".log", ".sv", ".py", ".json", ".csv", ".hex", ".md"}
work_names = {
    "ready-counterexample": "ready-level-counterexample-1030-a",
    "ready-candidate-first-failed": "ready-level-candidate-1030-a",
    "ready-candidate-final": "ready-level-candidate-1030-b",
    "polarity-counterexample": "hdmi-first-de-transient-native",
    "polarity-trained": "hdmi-trained-native-1030-a",
    "wrapper-wire-e2e": "ready-wrapper-e2e-1030-a",
}
for label, name in work_names.items():
    for path in sorted((VIS / name).iterdir()):
        if path.is_file() and path.suffix in allowed:
            note = None
            if label == "ready-candidate-first-failed" and path.name == "tb_ms7200_ready_level.sv":
                assert digest(path.read_bytes()) == "6cab7907734e361b68e4acd961aa7c7fe50ffabf5881b09c2f69d68baca88ad9"
                note = "ReconstructedFromExactInversePatchAndHashVerified; bytes match the original failed run InputSHA256."
            store(path, "simulations/" + label + "/" + path.name, note)
for name in ("tb_hdmi_first_de_transient.sv", "run_hdmi_first_de_transient.py"):
    store(VIS / name, "simulations/polarity-counterexample/" + name)

build = load(PROJECT / "build/hdmi-uart-diagnostic/trained-pds-1030-a/build-plan.json")
sources = set(build["InputSHA256"])
sources.update((
    "rtl/experimental/ms7200_1080p30_ctl.v", "rtl/experimental/ms72xx_observed_ctl.v",
    "rtl/experimental/hdmi1080_input_status_cdc.v", "board/hdmi_uart_input_diag.v",
    "tests/tb_ms7200_ready_level.sv", "tests/tb_hdmi_input_polarity_training.sv",
    "tests/tb_hdmi_input_training_raster.sv", "tests/tb_board1080_input_status_cdc.sv",
    "tests/tb_ms72xx_observed_e2e.sv", "tools/run_ms7200_ready_level_sim.py",
    "tools/run_hdmi_input_training_sim.py", "tools/run_hdmi_uart_sim.py",
    "tools/run_ms72xx_checked_sim.py", "tools/simulation_tools.py",
    "tools/run_gamma_pipeline_d5_sim.py", "tools/prepare_gamma_pipeline_d5.py",
))
for name in sorted(sources):
    path = PROJECT / name
    if name in build["InputSHA256"]:
        assert digest(path.read_bytes()) == build["InputSHA256"][name], "current candidate source drift: " + name
    store(path, "source-inputs/" + name)
store(Path(__file__), "audit-scripts/record_hdmi_trained_sims.py")

ready_counter = load(VIS / work_names["ready-counterexample"] / "counterexample-result.json")
ready_a = load(VIS / work_names["ready-candidate-first-failed"] / "simulation-result.json")
ready_b = load(VIS / work_names["ready-candidate-final"] / "simulation-result.json")
polarity_counter = load(VIS / work_names["polarity-counterexample"] / "simulation-result.json")
trained = load(VIS / work_names["polarity-trained"] / "simulation-result.json")
wrapper = load(VIS / work_names["wrapper-wire-e2e"] / "simulation-result.json")
assert ready_counter["Passed"] and not ready_a["Passed"] and ready_b["Passed"]
assert polarity_counter["Passed"] and trained["Passed"] and wrapper["Passed"]
assert trained["SourceDrift"] == [] and ready_b["InputDrift"] == [] and wrapper["SourceDrift"] == []

# Independently bind every suite input to an actual packaged original, including
# the reconstructed failed test. Absolute original paths stay provenance only.
by_raw_hash = {}
for row in files:
    by_raw_hash.setdefault(row["SourceSHA256"], []).append(row["File"])
suite_bindings = {}
for label, report in (("ready-counterexample", ready_counter), ("ready-candidate-first-failed", ready_a),
                      ("ready-candidate-final", ready_b), ("polarity-counterexample", polarity_counter),
                      ("polarity-trained", trained), ("wrapper-wire-e2e", wrapper)):
    inputs = report.get("InputSHA256", report.get("SourceSHA256"))
    bindings = {}
    for name, wanted in inputs.items():
        assert wanted in by_raw_hash, "suite source not preserved: " + label + " " + name
        bindings[name] = dict(SHA256=wanted, PackagedMatches=by_raw_hash[wanted])
    suite_bindings[label] = bindings

progress = dict(
    Schema="hdmi-trained-simulation-progress-v1", CreatedUTC=datetime.now(timezone.utc).isoformat(),
    Target="hdmi_uart_trained_diag", SimulationEvidenceSealed=True,
    HardwareAccessedByThisPackage=False, PDSExecutedByThisPackage=False,
    BitstreamGeneratedByThisPackage=False, HardwareReleaseAllowed=False,
    ReadyCounterexample={"Reproduced": True, "Summary": ready_counter["Summary"],
                         "Scope": "Unchanged original receiver, transaction response model; no wire-level I2C."},
    ReadyCandidate={"Passed": True, "Scenarios": 7, "Summary": ready_b["Summary"],
                    "Original311RegisterCommandsUnchanged": ready_b["SourceAudit"]["All311RegisterCommandsUnchanged"],
                    "FirstFailedAttemptPreserved": True,
                    "FirstFailureExplanation": "The first test checked ready_reads after 60 extra cycles of legitimate post-completion polling. The final test records ready_reads at actual completion; candidate RTL and runner bytes are identical in both attempts.",
                    "FirstFailedTBRecovery": "Exact inverse patch reconstructed bytes matching original InputSHA256 6cab7907734e361b68e4acd961aa7c7fe50ffabf5881b09c2f69d68baca88ad9."},
    FirstDECounterexample={"Reproduced": True, "Summary": polarity_counter["Summary"],
                           "Stimulus": "Only the transient instance receives opposite HS/VS for one first-DE PCLK sample; all later samples follow exact 2200x1125/1920x1080 at nominal 74.25 MHz.",
                           "RawFieldMapping": {"clean": "Original frozen observer, no injected transient.",
                                               "transient": "Original frozen observer, one first-DE opposite-HS/VS sample."}},
    TrainedPolarity={"Passed": True, "DirectedCases": trained["Suites"]["directed"]["Cases"],
                    "CompleteRasterAB": trained["Suites"]["raster"],
                    "OriginalNativeTBWithOnlyDUTNameChanged": trained["Suites"]["native"],
                    "RawRasterFieldMapping": {"clean": "New hdmi1080_input_status_trained receives the same one-sample first-DE opposite-HS/VS transient as the old instance.",
                                              "transient": "Original frozen hdmi1080_input_status_cdc receives the same one-sample transient. Both inputs are identical."},
                    "TrainingBoundary": "Two consecutive valid observed DE segments of exactly WIDTH samples and stable HS/VS train polarity. Blank periods and stopped PCLK may preserve the first candidate. The logic does not separately prove a physical source-line start after reset release inside DE; ordinary short partial segments are rejected. This is digital training, not PHY qualification."},
    WrapperWireE2E={"Passed": True, "Summary": wrapper["Summary"],
                   "WireTransactions": wrapper["WireTraceAudit"]["Transactions"],
                   "SuccessfulTelemetryRowsIndependentlyVerified": wrapper["IndependentWireTelemetryRowsVerified"],
                   "TransactionDriverStub": False, "WireLevelI2CExecuted": True},
    SuiteSourceBindings=suite_bindings,
    SourceSnapshotSHA256={name: digest((PROJECT / name).read_bytes()) for name in sorted(sources)},
    Limits=[
        "Counterexamples establish possible digital failure mechanisms. They do not prove those exact transients or register semantics occurred in physical hardware.",
        "This evidence package contains native simulation and source snapshots only; candidate PDS/CDC/STA evidence, if obtained, is a separately bound package.",
        "No candidate bitstream or download is performed by this package. External AC, physical CDC/MTBF, actual input pixel payload, DDR and corrected display remain separate.",
        "Absolute paths in original logs and runners are preserved as provenance; they are not rewritten into portable replay claims.",
    ],
)
dump(OUT / "sim-progress.json", progress)
progress_raw = (OUT / "sim-progress.json").read_bytes()
files.append(dict(File="sim-progress.json", Bytes=len(progress_raw), SHA256=digest(progress_raw),
                  Source=str(OUT / "sim-progress.json"), SourceBytes=len(progress_raw),
                  SourceSHA256=digest(progress_raw), Encoding="identity",
                  Note="Generated summary from the unmodified native reports and independently verified packaged source hashes."))

manifest = dict(Schema="hdmi-trained-simulation-evidence-manifest-v1",
                CreatedUTC=datetime.now(timezone.utc).isoformat(), Files=files,
                FileCount=len(files), StoredBytes=sum(row["Bytes"] for row in files),
                OriginalBytes=sum(row["SourceBytes"] for row in files),
                HardwareAccessed=False, PDSExecuted=False, BitstreamGenerated=False,
                Notes="Only root native logs, SV/Python/JSON/CSV/HEX and supporting README files are stored. No xsim.dir, PB, WDB or other simulator cache is packaged. Gzip entries decompress exactly to SourceSHA256; identity entries are byte-for-byte copies. sim-progress.json is a generated summary whose bytes are also bound here.")
dump(OUT / "manifest.json", manifest)
for row in files:
    path = OUT / row["File"]
    data = path.read_bytes()
    assert len(data) == row["Bytes"] and digest(data) == row["SHA256"]
    raw = gzip.decompress(data) if row["Encoding"] == "gzip" else data
    assert len(raw) == row["SourceBytes"] and digest(raw) == row["SourceSHA256"]
print(json.dumps(dict(Package=str(OUT), FileCount=len(files), StoredBytes=manifest["StoredBytes"],
                     ManifestSHA256=digest((OUT / "manifest.json").read_bytes()),
                     ProgressSHA256=digest((OUT / "sim-progress.json").read_bytes()),
                     AllStoredAndOriginalHashesVerified=True)))
