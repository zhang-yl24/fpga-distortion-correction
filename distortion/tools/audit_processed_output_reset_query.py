"""Verify the five exact reset query groups in a successful native receipt.

Names/counts come from Timing-5001 evidence, never Tcl opaque handle lengths.
This verifies query identity only; it does not authorize an exception or prove
entry connectivity, removal effects, final timing or physical CDC properties.
"""
from pathlib import Path
import argparse
import json

import prepare_ddr_native_reset_scope as native
import audit_processed_output_reset as common
import prepare_processed_output_reset_scope as proposal


require, sha = common.require, common.sha


def match_queries(queries, records):
    require(len(queries) == 5 and sorted(q["ExpectedTargetCount"] for q in queries) == [1, 1, 7, 14, 104],
            "expected five reset groups are missing")
    expected_patterns, proof = set(), []
    for query in queries:
        require(query["ExpectedFromCount"] == 1 and query["ExpectedNativeFromNames"] == ["t:" + query["Source"]]
                and query["ExpectedNativeToNames"] == ["t:" + name for name in query["Targets"]],
                "expected native names differ from the source/target inventory")
        for role, pattern_key, names_key, count_key in (
                ("from", "FromRegex", "ExpectedNativeFromNames", "ExpectedFromCount"),
                ("to", "ToRegex", "ExpectedNativeToNames", "ExpectedTargetCount")):
            pattern, names, count = query[pattern_key], query[names_key], query[count_key]
            require(pattern not in expected_patterns, "duplicate expected query pattern")
            expected_patterns.add(pattern)
            require(len(names) == len(set(names)) == count, "expected name count is inconsistent")
            matched = [r for r in records if r["Pattern"] == pattern]
            require(len(matched) == 1, "native query is missing or duplicated: " + query["Source"] + ":" + role)
            record = matched[0]
            require(record["Count"] == count and set(record["NativeNames"]) == set(names),
                    "native exact name/count mismatch: " + query["Source"] + ":" + role)
            proof.append({"Source": query["Source"], "Role": role, "EntryRDC": query["EntryRDC"],
                          "NativeEvidence": record})
    require(len(records) == 10 and {r["Pattern"] for r in records} == expected_patterns,
            "unexpected native pin queries in the isolated query stage")
    require(sum(p["NativeEvidence"]["Count"] for p in proof) == 132, "total object count differs")
    return proof


def audit(plan_path, receipt_path):
    plan_path, receipt_path = Path(plan_path).resolve(), Path(receipt_path).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    require(plan.get("Schema") == "processed-output-reset-scope-proposal-v1", "unexpected proposal schema")
    require(receipt.get("Schema") == "processed-output-isolated-physical-v1", "unexpected native receipt schema")
    require(receipt.get("ExecutionPassed") is True and receipt.get("ExitCode") == 0
            and receipt.get("TimedOut") is False and receipt.get("InputDrift") == []
            and receipt.get("Diagnostics") == [] and receipt.get("CompletionMarker") is True,
            "native query stage did not complete cleanly")
    require(receipt.get("HardwareAccessed") is False and receipt.get("BitstreamRequested") is False,
            "unexpected hardware operation in query stage")
    require(receipt["SourceADFSHA256"] == receipt["ResultADFSHA256"], "read-only query stage changed the loaded ADF")
    watched = {plan_path: sha(plan_path), receipt_path: sha(receipt_path)}
    watched[Path(proposal.__file__).resolve()] = plan["ToolSHA256"]
    for name, digest in plan["FilesSHA256"].items():
        path = (plan_path.parent / name).resolve()
        require(path.is_relative_to(plan_path.parent), "proposal artifact escaped directory")
        watched[path] = digest
    watched[Path(plan["Report"]["Path"])] = plan["Report"]["SHA256"]
    for name, digest in plan["HelperSHA256"].items():
        watched[Path(name)] = digest
    for name, digest in receipt["InputSHA256"].items():
        path = Path(name)
        require(path not in watched or watched[path] == digest, "conflicting input hashes")
        watched[path] = digest
    for name, digest in receipt["Artifacts"].items():
        path = (receipt_path.parent / name).resolve()
        require(path.is_relative_to(receipt_path.parent), "native artifact escaped directory")
        require(path not in watched or watched[path] == digest, "conflicting artifact hashes")
        watched[path] = digest
    for path, digest in watched.items():
        require(path.is_file() and sha(path) == digest, "bound input/artifact drift: " + str(path))
    body = (plan_path.parent / "query-body.tcl").read_text(encoding="ascii")
    require(receipt.get("Body") == body, "native body differs from prepared exact queries")
    log_path = receipt_path.parent / "stdout.log"
    require(log_path in watched, "native log is not hash-bound by receipt")
    proof = match_queries(plan["NativeQueries"], native.parse_native_matches(log_path))
    for path, digest in watched.items():
        require(sha(path) == digest, "input/artifact changed during query audit")
    return {"Schema": "processed-output-reset-query-audit-v1", "NativeQueriesVerified": True,
            "ExactGroups": 5, "SourceObjects": 5, "TargetObjects": 127,
            "NativeMatchRecords": 10, "NativeNameProof": proof,
            "Plan": {"Path": str(plan_path), "SHA256": sha(plan_path)},
            "Receipt": {"Path": str(receipt_path), "SHA256": sha(receipt_path)},
            "QueryLog": {"Path": str(log_path), "SHA256": sha(log_path)},
            "LoadedADFSHA256": receipt["SourceADFSHA256"],
            "AllBoundInputArtifactsRechecked": len(watched), "InputDrift": [],
            "NativeParserSHA256": sha(native.__file__), "AuditToolSHA256": sha(__file__),
            "EntryConnectivityVerified": False, "TimingExceptionApproved": False,
            "ConstraintsApplied": False, "HardwareAccessed": False, "HardwareReleaseAllowed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists(), "output must be new")
    result = audit(args.plan, args.receipt)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("NativeQueriesVerified", "ExactGroups", "SourceObjects", "TargetObjects")}, indent=2))


if __name__ == "__main__":
    main()
