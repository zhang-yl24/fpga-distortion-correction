"""Read-only audit of two pinned PDS gate-preparse log patterns. No CAD/manifest writes."""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "build/offline-20261024"
MAIN = "corrected_gamma_pipeline_d5"
RAW720 = "raw_camera_capture_cam2_guarded_720p15"
SCRIPTS = {
    MAIN: {"script_in_work": "reseed.tcl",
           "script_sha256": "e12f8602ca172c605b0a4829a3fa2c7f3a9f9cdf5bb31f5d0c06ebd6d673aa5e",
           "canonical_source": "board/build-corrected_gamma_pipeline_d5.tcl",
           "canonical_sha256": "325d305c7f9fe3e869038bbe7e813717899da48586bcbff7b9b1a19c6174a88a"},
    RAW720: {"canonical_source": "board/build-raw_camera_capture_cam2_guarded_720p15.tcl",
             "script_sha256": "6664e7af055ecf44a4d1bb5391ca3abaf0958c814c67295174fc63e8ddafe914",
             "canonical_sha256": "6664e7af055ecf44a4d1bb5391ca3abaf0958c814c67295174fc63e8ddafe914"},
}
STAGES = ("compile", "synthesize", "dev_map", "pnr", "report_timing", "gen_bit_stream")
CANONICAL_MAIN = "canonical_main"
RESEEDED_MAIN = "main_reseed"
RAW720_ROLE = "raw720"
ERROR = re.compile(r"(?im)^\s*[EF]:|\bERROR\b|\bFATAL\b")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _one(values, label):
    if len(values) != 1:
        raise ValueError("exactly one pinned script anchor required: " + label)
    return values[0]


def script_role(target, role=None):
    # Preserve the historical helper API's main/reseed default. New build
    # callers explicitly request canonical_main; never infer a role from files.
    if target == MAIN and role in (None, CANONICAL_MAIN, RESEEDED_MAIN):
        return RESEEDED_MAIN if role is None else role
    if target == RAW720 and role in (None, RAW720_ROLE):
        return RAW720_ROLE
    raise ValueError("only an explicitly supported target/script role is allowed")


def script_context(work, target, role=None):
    if target not in SCRIPTS:
        raise ValueError("only the two explicitly pinned targets are supported")
    role = script_role(target, role)
    fixed = SCRIPTS[target]
    canonical = ROOT / fixed["canonical_source"]
    derived = role == RESEEDED_MAIN
    script = work / fixed["script_in_work"] if derived else canonical
    script_hash = fixed["script_sha256"] if derived else fixed["canonical_sha256"]
    if sha(canonical) != fixed["canonical_sha256"] or sha(script) != script_hash:
        raise ValueError("pinned current CAD script bytes changed")
    text = script.read_text(encoding="utf-8")
    if derived and text != canonical.read_text(encoding="utf-8").replace("-gplace_seed 2", "-gplace_seed 3"):
        raise ValueError("main CAD script differs beyond its fixed seed3 derivation")
    lines = text.splitlines()
    numbered = list(enumerate((line.strip() for line in lines), 1))
    locate = lambda predicate, label: _one([n for n, line in numbered if predicate(line)], label)
    errors = re.findall(r'\berror "([^"\r\n]+)"', text)
    if len(errors) != 2:
        raise ValueError("pinned gate must have exactly its two error messages")
    if f"set final_timing_path [file join [pwd] report_timing {target}.rtr]" not in lines:
        raise ValueError("gate report filename is not the fixed target")
    positions = (
        locate(lambda line: line.startswith("if {![file isfile $final_timing_path]}"), "missing report condition"),
        locate(lambda line: line == "set final_timing_handle [open $final_timing_path r]", "report open"),
        locate(lambda line: line == "set final_timing_text [read $final_timing_handle]", "report read"),
        locate(lambda line: line == "close $final_timing_handle", "report close"),
        locate(lambda line: line.startswith("foreach ") and "$final_timing_text" in line, "summary loop"),
        locate(lambda line: line.startswith("if {") and "!= 1" in line and "||" in line, "final summary condition"),
    )
    missing = (script.parent / "report_timing" / (target + ".rtr")).as_posix()
    messages = ("E: " + errors[0], f'E: couldn\'t open "{missing}": no such file or directory',
                'E: can\'t read "final_timing_handle": no such variable',
                'E: can\'t read "final_timing_handle": no such variable',
                'E: can\'t read "final_timing_text": no such variable', "E: " + errors[1])
    expected = []
    for message, line in zip(messages, positions):
        expected.extend((message, f'E: Flow-0163: Failed to parse file "{script}" at line {line}. Check if the command options or arguments are valid.'))
    commands = {stage: _one([line for _, line in numbered if line == stage or line.startswith(stage + " ")], stage)
                for stage in STAGES}
    return script, expected, commands


def audit_text(stdout, stderr, *, work, target, script, expected_errors, commands):
    """Pure classifier; caller must obtain its context from pinned script bytes."""
    if stderr.strip():
        raise ValueError("stderr is not empty; no preparse exception applies to stderr")
    lines = stdout.splitlines()
    first = next((i for i, line in enumerate(lines) if line.startswith("Analyzing project file ")), None)
    boundary = f"Analyzing project file '{work.as_posix()}/{target}.pds'."
    if first is None or lines[first] != boundary:
        raise ValueError("first actual Analyzing boundary is missing or names another project")
    prefix, suffix = lines[:first], lines[first:]
    observed = [line for line in prefix if line.startswith("E:")]
    if observed != expected_errors:
        raise ValueError("pre-Analyzing diagnostics differ from the exact twelve pinned gate errors")
    for line in prefix:
        if line in expected_errors or not line:
            continue
        if line == "Compiling architecture definition.":
            continue
        if re.fullmatch(r"License checkout: fabric_shell from .+\.lic", line):
            continue
        if re.fullmatch(r"W: Warning : The license will invalid in \d+ days\. In order not to affect your usage, please update the license in time\.", line):
            continue
        raise ValueError("unknown pre-Analyzing prefix line")
    if ERROR.search("\n".join(suffix)):
        raise ValueError("actual execution suffix contains E/F/ERROR/FATAL")
    found, previous = [], first
    for stage in STAGES:
        command = commands[stage]
        starts = [i for i, line in enumerate(lines) if i >= first and line == "Executing : " + command]
        successes = [i for i, line in enumerate(lines) if i >= first and line == "Executing : " + command + " successfully."]
        begin = _one(starts, stage + " actual start")
        end = _one(successes, stage + " named success")
        if not previous < begin < end:
            raise ValueError("actual six-stage start/success order differs")
        found.append({"Stage": stage, "Command": command, "StartLogLine": begin + 1, "SuccessLogLine": end + 1})
        previous = end
    return {"Passed": True, "Target": target, "CADScript": str(script), "FirstActualAnalyzingLogLine": first + 1,
            "ExactGatePreparseErrorsAllowed": 12, "ActualStages": found,
            "ActualExecutionSuffixErrorFree": True, "ActualBitGenerationNamedSuccess": True,
            "PostBuildLogAuditOnly": True, "PreBitGateExecutionProven": False,
            "NativeExitVerifiedByThisHelper": False, "FinalTimingVerifiedByThisHelper": False,
            "ValidatedManifestWritten": False, "HardwareAccessed": False,
            "Limits": "Only the pinned pre-Analyzing twelve-error parse pattern is classified. This does not prove custom Tcl gate execution before bit generation. Native exit, final saved-DB timing, source/pins/bit/simulation hashes require independent download-time validation; no artifact or historical result is promoted here."}


def audit_gate_log(build_dir, target, role=None):
    work = Path(build_dir).resolve()
    if not work.is_dir() or not work.is_relative_to(APPROVED.resolve()):
        raise ValueError("existing build under approved scratch required")
    role = script_role(target, role)
    script, expected, commands = script_context(work, target, role)
    out, err = work / "build-stdout.log", work / "build-stderr.log"
    result = audit_text(out.read_text(encoding="utf-8", errors="replace"),
                        err.read_text(encoding="utf-8", errors="replace"), work=work, target=target,
                        script=script, expected_errors=expected, commands=commands)
    result.update(CADScriptRole=role, CADScriptSHA256=sha(script), StdoutSHA256=sha(out), StderrSHA256=sha(err), BuildDirectory=str(work))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--target", choices=tuple(SCRIPTS), required=True)
    parser.add_argument("--script-role", choices=(CANONICAL_MAIN, RESEEDED_MAIN, RAW720_ROLE))
    args = parser.parse_args()
    try:
        result = audit_gate_log(args.build_dir, args.target, args.script_role)
    except (ValueError, OSError) as exc:
        print(json.dumps({"Passed": False, "Error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
