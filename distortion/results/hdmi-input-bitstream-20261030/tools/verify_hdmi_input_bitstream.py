"""Read-only verification of the exact 2026-10-30 HDMI observer export.

No EDA or hardware operation is performed. A successful receipt verifies the
frozen offline artifact and its recorded gates, not physical video acceptance.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import re

import prepare_hdmi_input_bitstream as prepare

BIT_BYTES = 3_791_112
BIT_SHA256 = "4aa42d6fc582385ea584c68a86d796bc26fcc8568c337abe053a2e6a41ad63dc"
CLASSIFIER_ERROR = "AssertionError: ['compile', 'synthesize', 'dev_map', 'pnr', 'report_timing', 'gen_bit_stream']"
AUDIT_MARKER = "HDMI_INPUT_PRE_BIT_AUDIT_PASS " + prepare.ADF_SHA256
COMPLETE_MARKER = "HDMI_INPUT_BITSTREAM_COMPLETE"
REPORT = "report_timing/" + prepare.TARGET + ".rtr"
EXCEPTIONS = "report_timing/" + prepare.TARGET + "_exception.rtr"
BITSTREAM = "generate_bitstream/" + prepare.TARGET + ".sbit"
PRE_BIT_EVIDENCE = ("bitstream-plan.json", "audited-final.adf", "export.tcl", REPORT, EXCEPTIONS)
require, sha, read_text = prepare.require, prepare.sha, prepare.read_text


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def exact(value, expected, message):
    # JSON bools must not compare equal to integer counters or status codes.
    require(type(value) is type(expected) and value == expected, message)


def input_adf(command, work):
    matches = re.findall(r"(?:^|\s)-input_db_file\s+(?:\{([^{}]+)\}|(\S+))", command)
    require(len(matches) == 1, "exactly one input_db_file is required")
    name = matches[0][0] or matches[0][1]
    require(Path(name).resolve() == work / "audited-final.adf", "generation source ADF path differs")


def actual_stages(text, work):
    """PDS Executing lines include declarations; Process lines mean execution."""
    events, commands = [], []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Process "):
            match = re.fullmatch(r'Process "([^"]+)" (started|done)\.', line)
            require(match is not None, "unrecognized actual process event")
            events.append((match[1], match[2]))
        elif line.startswith("HDMI_INPUT_PRE_BIT_AUDIT_PASS"):
            require(line == AUDIT_MARKER, "pre-bit audit marker differs")
            events.append(("runtime_native_audit", "pass"))
        elif line.startswith(COMPLETE_MARKER):
            require(line == COMPLETE_MARKER, "completion marker differs")
            events.append(("bitstream", "complete"))
        match = re.fullmatch(r"Executing\s*:\s*(gen_bit_stream\s+.+)", line)
        if match and not line.endswith(" successfully."):
            commands.append(match[1])
            events.append(("gen_bit_stream", "command"))
    expected = [("Report Timing", "started"), ("Report Timing", "done"),
                ("runtime_native_audit", "pass"), ("gen_bit_stream", "command"),
                ("Generate Bitstream", "started"),
                ("Generate Bitstream", "done"), ("bitstream", "complete")]
    require(events == expected, "actual stage order differs from STA, audit, bitstream, completion")
    require(len(commands) == 1, "exactly one actual gen_bit_stream command is required")
    input_adf(commands[0], work)
    require(not re.search(r"(?im)^\s*(?:[EF]:|ERROR\b|FATAL\b|Traceback\b)", text),
            "native stdout contains an error")
    return {"ActualStages": ["report_timing", "runtime_native_audit", "gen_bit_stream"],
            "ProcessEvents": [{"Stage": stage, "Event": event} for stage, event in events],
            "GenerationInputADF": str(work / "audited-final.adf")}


def bitstream_header(data):
    prefix = bytes.fromhex("00090ff00ff00ff00ff000") + b"PANGO MICROSYSTEMS, INC.\0\1"
    require(data.startswith(prefix), "bitstream header prefix differs")
    offset, values = len(prefix), {}
    for tag, name in ((b"a", "Design"), (b"b", "Device"), (b"c", "Date"),
                      (b"d", "Time"), (b"e", "Generator"), (b"f", "Version")):
        require(data[offset:offset + 1] == tag and offset + 3 <= len(data), "bitstream header field differs")
        count = int.from_bytes(data[offset + 1:offset + 3], "big")
        require(count > 0 and offset + 3 + count <= len(data), "bitstream header field is truncated")
        raw = data[offset + 3:offset + 3 + count]
        require(raw.endswith(b"\0") and b"\0" not in raw[:-1], "bitstream header text differs")
        try:
            values[name] = raw[:-1].decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("non-ASCII bitstream header") from error
        offset += 3 + count
    require(data[offset:offset + 3] == b"ghi", "bitstream header terminator differs")
    for name, expected in (("Design", prepare.TARGET), ("Device", "Logos2-PG2L100H--6-FBG676"),
                           ("Generator", "Fabric Compiler"), ("Version", "2023.2-SP3<154097>")):
        require(values[name] == expected, "bitstream identity differs: " + name)
    return values


def check_execution(work, plan):
    receipt = read_json(work / "export-result.json")
    require(receipt.get("Schema") == "hdmi-input-bitstream-execution-v1" and
            receipt.get("Target") == prepare.TARGET and receipt.get("Command") == plan["Command"] and
            receipt.get("SourceADFSHA256") == prepare.ADF_SHA256,
            "native execution receipt identity differs")
    exact(receipt.get("ReturnCode"), 0, "native execution did not exit zero")
    exact(receipt.get("HardwareAccessed"), False, "execution declared hardware access")
    hashes = {name: sha(work / name) for name in ("native-stdout.log", "native-stderr.log")}
    require(receipt.get("LogSHA256") == hashes, "native execution log hashes differ")
    require(not (work / "native-stderr.log").read_bytes().strip(), "native stderr is not empty")
    reconciled = receipt.get("Passed") is False and receipt.get("Error") == CLASSIFIER_ERROR
    if reconciled:
        explanation = "The original wrapper counted PDS pre-parser Executing declarations as stages. Its failed receipt is preserved; actual Process started/done events are independently verified here."
    else:
        exact(receipt.get("Passed"), True, "unrecognized execution receipt failure")
        require(not receipt.get("Error"), "execution receipt contains an error")
        explanation = None
    result = actual_stages(read_text(work / "native-stdout.log"), work)
    result.update(PassedAsRecorded=receipt["Passed"], ErrorAsRecorded=receipt.get("Error"),
                  StageClassifierFailureReconciled=reconciled, Reconciliation=explanation)
    return result


def verify(work):
    work = Path(work).resolve()
    plan = read_json(work / "bitstream-plan.json")
    project = Path(plan["ProjectRoot"]).resolve()
    require(project == prepare.ROOT.resolve() and work == Path(plan["WorkDirectory"]).resolve() and
            work.parent == project / "build/hdmi-uart-diagnostic" and work.name.startswith("input-bit-"),
            "verification work directory identity differs")
    prepare.verify_inputs(project, work, plan)
    native = prepare.compare_native(work / "baseline.rtr", work / "baseline-exceptions.rtr",
                                    work / REPORT, work / EXCEPTIONS)
    require(plan.get("SourceNativeAudit") == native, "prepared native audit differs")
    audit = read_json(work / "pre-bit-audit.json")
    expected = dict(Schema="hdmi-input-pre-bit-audit-v1", AuditPassed=True, Target=prepare.TARGET,
                    FinalADFSHA256=prepare.ADF_SHA256, HardwareAccessed=False,
                    HardwareReleaseAllowed=False, **native)
    for name, wanted in expected.items():
        exact(audit.get(name), wanted, "pre-bit audit value differs: " + name)
    require(audit.get("EvidenceSHA256") == {name: sha(work / name) for name in PRE_BIT_EVIDENCE},
            "pre-bit audit evidence hashes differ")
    execution = check_execution(work, plan)
    commands = re.findall(r"(?m)^\s*gen_bit_stream\s+(.+)$", read_text(work / "export.tcl"))
    require(len(commands) == 1, "export Tcl requires exactly one gen_bit_stream command")
    input_adf(commands[0], work)
    data = (work / BITSTREAM).read_bytes()
    require(len(data) == BIT_BYTES and prepare.digest(data) == BIT_SHA256, "fixed exported bitstream bytes differ")
    header = bitstream_header(data)
    bgr_name = "generate_bitstream/" + prepare.TARGET + ".bgr"
    bgr = work / bgr_name
    if bgr.exists():
        text = read_text(bgr)
        require("Generating Programming File done." in text and
                not re.search(r"(?im)^\s*(?:[EF]:|ERROR\b|FATAL\b)", text), "bitstream generation report did not succeed")
        commands = re.findall(r"(?m)^Flow Command:\s*(gen_bit_stream\s+.+)$", text)
        require(len(commands) == 1, "generation report command differs")
        input_adf(commands[0], work)
    evidence = {name: sha(work / name) for name in
                (*plan["WorkInputSHA256"], "bitstream-plan.json", "pre-bit-audit.json",
                 "export-result.json", "native-stdout.log", "native-stderr.log", REPORT, EXCEPTIONS, BITSTREAM)}
    if bgr.exists():
        evidence[bgr_name] = sha(bgr)
    prepare.verify_inputs(project, work, plan)
    require(all(sha(work / name) == wanted for name, wanted in evidence.items()), "artifact changed during verification")
    return dict(Schema="hdmi-input-bitstream-verification-v1", Passed=True, Target=prepare.TARGET,
                CheckedUTC=datetime.now(timezone.utc).isoformat(), WorkDirectory=str(work),
                FinalADFSHA256=prepare.ADF_SHA256, SourceBindings=len(plan["ProjectInputSHA256"]),
                PreparedBindings=len(plan["WorkInputSHA256"]), NativeAudit=native,
                ExecutionReceipt=execution, GenerationReportPresent=bgr.exists(),
                Bitstream={"Path": str(work / BITSTREAM), "Bytes": len(data), "SHA256": BIT_SHA256, "Header": header},
                EvidenceSHA256=evidence, VerifierSHA256=sha(__file__), HardwareAccessed=False,
                EDAExecutedByVerifier=False, HardwareReleaseAllowed=False,
                Limits="Exact offline observer export only; no new build, programmer access, physical CDC/AC acceptance, real input pixels, DDR or distortion verification.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("output must be a new file in an existing directory")
    result = verify(args.workdir)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"Passed": True, "BitstreamSHA256": BIT_SHA256, "Output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
