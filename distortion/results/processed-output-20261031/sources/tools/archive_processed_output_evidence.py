"""Archive completed independent processing/output evidence without running EDA.

Only self-authored source bytes and completed simulation/PDS text evidence are
copied. Vendor/IP bodies and routed databases remain local path/hash references.
The destination is exclusive. Existing failures are referenced, never removed.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil


PROJECT = Path(__file__).resolve().parents[1]
SIM_REPORT = "processed-output-simulation.json"
PATTERN_REPORT = "processed-output-pattern-simulation.json"
DEFAULT_INTEGRATION = PROJECT / "build/processed-output-integration/top-20261031-g"
PATTERN_RUNS = (
    ("pattern-small", PROJECT / "build/processed-output-pattern/small-20261031-b"),
    ("pattern-native", PROJECT / "build/processed-output-pattern/native-20261031-a"),
)
SOURCE_FILES = (
    "board/processed_output_top.v", "board/processed-output-sources.json",
    "board/processed-output-diagnostic.fdc", "board/board1080-synthetic.vh",
    "board/hdmi_tx_init.v", "board/ms7210_commands.vh",
    "rtl/experimental/processed_output_pattern.v", "rtl/reg16_i2c.v",
    "tools/prepare_processed_output.py", "tools/prepare_board1080_timing.py",
    "tools/run_processed_output_pattern_sim.py", "tools/run_processed_output_sim.py",
    "tools/run_processed_output_diagnostic.py", "tools/archive_processed_output_evidence.py",
    "tools/audit_processed_output_native.py", "tools/audit_board1080_pin_contract.py",
    "tools/audit_ddr_final_timing.py",
    "tests/tb_processed_output_pattern.sv", "tests/tb_processed_output.sv",
    "tests/processed_output_ip_stubs.sv", "tests/test_prepare_processed_output.py",
)
SIM_EVIDENCE_SUFFIXES = {".json", ".log", ".mem", ".csv", ".vh", ".png", ".tcl"}
# Native PDS text reports, in addition to the executor/audit JSON and logs.
# No HDL/IP/binary/database suffix is admitted by this evidence allowlist.
PDS_NATIVE_TEXT_SUFFIXES = {".cmr", ".snr", ".dmr", ".ccr", ".pcf", ".prr", ".prt", ".rtr", ".rtx", ".ror", ".plr", ".rur"}
PDS_EVIDENCE_SUFFIXES = {".json", ".log", ".rpt", ".txt", ".tcl"} | PDS_NATIVE_TEXT_SUFFIXES
DEFAULT_FAILURES = (
    "build/processed-output-pattern/small-20261031-a",
    *(f"build/processed-output-integration/top-20261031-{letter}" for letter in "abcde"),
    "build/processed-output/source-freeze-20261031-a",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value, parent, *, directory=False):
    path = Path(value).absolute()
    require(path == path.resolve() and path.is_relative_to(parent), "escaped or linked evidence path")
    require(path.is_dir() if directory else path.is_file(), "evidence path is missing: " + str(value))
    return path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def self_authored(name):
    parts = Path(name).parts
    return (bool(parts) and parts[0] in {"rtl", "tools", "tests", "model"}
            or name.startswith("board/") and name != "board/bringup_pll.v")


def local_reference(path):
    path = canonical(path, PROJECT.resolve())
    return {"LocalPath": str(path), "ProjectRelativePath": path.relative_to(PROJECT).as_posix(),
            "Bytes": path.stat().st_size, "SHA256": sha(path), "Copied": False}


def completed_simulation(work, report_name):
    work = canonical(work, PROJECT / "build", directory=True)
    report_file = work / report_name
    report = load(canonical(report_file, work))
    require(report.get("Passed") is True, "only completed passing simulation evidence may be archived as a success")
    require(report.get("HardwareAccessed") is False and report.get("PDSAccessed") is False,
            "unexpected physical operation in digital simulation evidence")
    require(report.get("SourceSHA256After", report.get("SourceSHA256")) == report.get("SourceSHA256"),
            "simulation source drift")
    require(not report.get("SourceDrift") and not report.get("FixtureDrift") and not report.get("SourceOrFixtureDrift"),
            "simulation reported source or fixture drift")
    require(report.get("FixtureSHA256After", report.get("FixtureSHA256")) == report.get("FixtureSHA256"),
            "simulation fixture hashes changed")
    require(all(command.get("ReturnCode") == 0 for command in report.get("Commands", []))
            and len(report.get("Commands", [])) == 3, "simulation native stages did not all complete")
    return work, report_file, report


def copy_bound(source, destination, *, compressed=False):
    """Write a new artifact, binding both original and encoded bytes."""
    original_hash = sha(source)
    original_size = source.stat().st_size
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as stream, destination.open("xb") as target:
        if compressed:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as encoded:
                shutil.copyfileobj(stream, encoded, 1 << 20)
        else:
            shutil.copyfileobj(stream, target, 1 << 20)
    require(sha(source) == original_hash and source.stat().st_size == original_size,
            "evidence changed while being copied: " + str(source))
    return {"Bytes": destination.stat().st_size, "SHA256": sha(destination),
            "Encoding": "gzip" if compressed else "identity", "OriginalBytes": original_size,
            "OriginalSHA256": original_hash, "Origin": str(source)}


def verify_archive(destination):
    """Read every artifact back, including decompressed payload hashes."""
    destination = canonical(destination, PROJECT / "results", directory=True)
    manifest = load(destination / "manifest.json")
    for relative, binding in manifest["Files"].items():
        file = canonical(destination / relative, destination)
        require(file.stat().st_size == binding["Bytes"] and sha(file) == binding["SHA256"],
                "archived bytes do not match manifest: " + relative)
        digest, count = hashlib.sha256(), 0
        opener = gzip.open if binding["Encoding"] == "gzip" else open
        with opener(file, "rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                count += len(chunk)
                digest.update(chunk)
        require(count == binding["OriginalBytes"] and digest.hexdigest() == binding["OriginalSHA256"],
                "archive original payload binding differs: " + relative)
    actual = {file.relative_to(destination).as_posix() for file in destination.rglob("*") if file.is_file()}
    require(actual == set(manifest["Files"]) | {"manifest.json"}, "unexpected artifact in exclusive archive")
    return {"ReadbackVerified": True, "Files": len(manifest["Files"]), "ManifestSHA256": sha(destination / "manifest.json")}


def archive(destination, integration_workdir=DEFAULT_INTEGRATION, pds_workdir=None, failure_workdirs=(), extra_files=()):
    project = PROJECT.resolve()
    destination = Path(destination).absolute()
    require(destination == destination.resolve() and destination.parent == project / "results"
            and not destination.exists(), "destination must be a new direct child of distortion/results")
    simulations = [(label, *completed_simulation(work, PATTERN_REPORT)) for label, work in PATTERN_RUNS]
    simulations.append(("integration", *completed_simulation(integration_workdir, SIM_REPORT)))
    sources = set(SOURCE_FILES)
    source_bindings, reference_bindings = {}, {}
    for label, work, report_file, report in simulations:
        for name, digest in report["SourceSHA256"].items():
            path = canonical(project / name, project)
            require(sha(path) == digest, "current source differs from completed run: " + name)
            if self_authored(name):
                require(name not in source_bindings or source_bindings[name] == digest, "runs bind different source versions")
                sources.add(name)
                source_bindings[name] = digest
            else:
                reference_bindings[name] = local_reference(path)
    pds = None
    if pds_workdir is not None:
        pds = canonical(pds_workdir, project / "build/processed-output", directory=True)
        require(pds.parent == project / "build/processed-output", "PDS work must be a direct diagnostic child")
        execution = load(canonical(pds / "execution-result.json", pds))
        require(execution.get("FinishedUTC") and execution.get("TimingAccepted") is False
                and execution.get("HardwareAccessed") is False and execution.get("BitstreamRequested") is False,
                "PDS receipt is incomplete or asserts unsupported acceptance")
        require(not execution.get("Cleanup", {}).get("TreeKillAttempted") or execution["Cleanup"].get("Complete"),
                "PDS owned process cleanup is incomplete")
    for name in sources:
        require(self_authored(name), "vendor/IP source cannot be copied")
        path = canonical(project / name, project)
        if name in source_bindings:
            require(sha(path) == source_bindings[name], "source snapshot binding drift")
    extra = [canonical(file, project) for file in extra_files]
    require(all(file.suffix in PDS_EVIDENCE_SUFFIXES for file in extra), "extra evidence must be text reports")
    failures = []
    failure_paths = [project / name for name in DEFAULT_FAILURES] + [Path(p) for p in failure_workdirs]
    seen_failures = set()
    for folder in failure_paths:
        if not folder.exists():
            continue
        folder = canonical(folder, project / "build", directory=True)
        if folder in seen_failures:
            continue
        seen_failures.add(folder)
        # Record only original text/fixture evidence; no compiler binaries or
        # vendor snapshots are copied or deleted. Hash metadata is sufficient.
        references = [local_reference(file) for file in sorted(folder.rglob("*"))
                      if file.is_file() and file.suffix in SIM_EVIDENCE_SUFFIXES
                      and not any(part in {"compiled", "xsim.dir"} for part in file.relative_to(folder).parts)]
        failures.append({"OriginalWorkDirectory": str(folder), "Files": references, "Copied": False, "Deleted": False})

    destination.mkdir()
    files, original_files = {}, {}

    def add(source, relative, *, compress=None):
        source = canonical(source, project)
        encoded = (source.suffix == ".log" or source.stat().st_size >= 131072 and source.suffix in
                   ({".csv", ".mem", ".txt", ".rpt"} | PDS_NATIVE_TEXT_SUFFIXES)) if compress is None else compress
        name = relative + (".gz" if encoded else "")
        require(name not in files and not Path(name).is_absolute() and ".." not in Path(name).parts,
                "duplicate or unsafe archive entry")
        files[name] = copy_bound(source, destination / name, compressed=encoded)
        original_files[str(source)] = files[name]["OriginalSHA256"]

    for name in sorted(sources):
        add(project / name, "sources/" + name, compress=False)
    run_summaries = {}
    for label, work, report_file, report in simulations:
        for file in sorted(work.iterdir()):
            if file.is_file() and file.suffix in SIM_EVIDENCE_SUFFIXES:
                add(file, "runs/" + label + "/" + file.name)
        # The include-only compiled copies contain self-authored code only;
        # preserve them as exact compiler inputs, without vendor/IP references.
        for binding in report.get("CompileBindings", {}).values():
            file = canonical(binding["CompiledPath"], work)
            require(sha(file) == binding["CompiledSHA256"], "compiled simulation input drift")
            add(file, "runs/" + label + "/" + file.relative_to(work).as_posix(), compress=False)
        for root in (work / "relocated-headers", work / "board"):
            if root.is_dir():
                for file in sorted(root.rglob("*.vh")):
                    relative = "runs/" + label + "/" + file.relative_to(work).as_posix()
                    if relative not in files:
                        add(file, relative, compress=False)
        run_summaries[label] = {"OriginalWorkDirectory": str(work), "Report": "runs/" + label + "/" + report_file.name,
                                "ReportSHA256": sha(report_file), "Summary": report.get("Summary"),
                                "Limits": report.get("Limits"), "Model": report.get("Model"), "Oracle": report.get("Oracle")}
    database_refs = []
    if pds is not None:
        for file in sorted(pds.rglob("*")):
            if not file.is_file():
                continue
            relative = file.relative_to(pds)
            if "compiled" in relative.parts:
                continue
            if file.suffix.casefold() == ".adf":
                database_refs.append(local_reference(file))
            elif file.suffix.casefold() in PDS_EVIDENCE_SUFFIXES:
                add(file, "pds/" + relative.as_posix())
    for index, file in enumerate(extra):
        add(file, f"extra/{index:02d}-" + file.name)
    for source, digest in original_files.items():
        require(sha(Path(source)) == digest, "original evidence drift before manifest freeze")
    manifest = {"Schema": "independent-processed-output-evidence-archive-v1",
                "ArchivedUTC": datetime.now(timezone.utc).isoformat(), "Destination": str(destination),
                "DigitalSimulationsPassed": True, "Runs": run_summaries, "SourceSHA256": source_bindings,
                "VendorReferencesOnly": reference_bindings, "PDSIncluded": pds is not None,
                "LocalDatabaseReferencesOnly": database_refs, "FailuresPreservedAtOriginalPaths": failures,
                "HardwareAccessedByArchiver": False, "EDAExecutedByArchiver": False,
                "TimingAccepted": False, "HardwareReleaseAllowed": False,
                "ReadbackRequired": True, "ManifestSelfHashExcluded": True, "Files": files,
                "Limits": ["Controlled synthetic source and small integration test; not current camera capture or calibration.",
                           "Native pattern test alone is not native processing/output throughput.",
                           "Runtime faults were injected at the first source AW before source commit; display-lease quarantine was not independently covered.",
                           "Integration normal drain uses private test-only grant withholding; the board top has no host stop API.",
                           "Native PDS exit, if included, is not timing or physical acceptance.",
                           "Vendor/IP body and routed database bytes are not archived by this tool."]}
    with (destination / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    checked = verify_archive(destination)
    return {"Archived": True, "Manifest": str(destination / "manifest.json"), **checked}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--integration-workdir", type=Path, default=DEFAULT_INTEGRATION)
    parser.add_argument("--pds-workdir", type=Path)
    parser.add_argument("--failure-workdir", type=Path, action="append", default=[])
    parser.add_argument("--extra-file", type=Path, action="append", default=[])
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = (verify_archive(args.destination) if args.verify_only else archive(
            args.destination, args.integration_workdir, args.pds_workdir, args.failure_workdir, args.extra_file))
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(json.dumps({"Archived": False, "Error": str(error), "EDAExecutedByArchiver": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
