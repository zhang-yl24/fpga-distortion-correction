"""Read-only reset evidence for the independent processed-output candidate.

The existing strict public-netlist checker is reused after replacing only the
verified module declaration token in memory. No cell, net, file or old checker
is changed. The actual input bytes and the normalization are recorded. This
checks connectivity and matching vendor source bytes; it grants no exception.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

import audit_ddr_entry_reset_netlist as entry
import prepare_processed_output as candidate


PROJECT = Path(__file__).resolve().parents[1]
VENDOR = (PROJECT.parent / "vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/"
          "ddr3_test/ipcore/ddr3_test")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_entry_text(text):
    # Preserve comments/line counts while finding the actual declaration.
    clean = re.sub(r"/\*.*?\*/|//[^\n]*|\(\*.*?\*\)",
                   lambda m: "".join("\n" if c == "\n" else " " for c in m[0]),
                   text, flags=re.DOTALL)
    declarations = list(re.finditer(r"(?m)^module\s+(\w+)\b", clean))
    require(len(declarations) == 1 and declarations[0][1] == "processed_output_top",
            "one actual processed_output_top module is required")
    require(len(re.findall(r"(?m)^endmodule\b", clean)) == 1,
            "one endmodule is required")
    token = declarations[0].span(1)
    normalized = text[:token[0]] + "board1080_top" + text[token[1]:]
    result = entry.audit_text(normalized)
    result["TopDeclarationAdapter"] = {
        "ActualTop": "processed_output_top", "CheckerTop": "board1080_top",
        "Replacements": 1, "OnlyModuleDeclarationTokenChangedInMemory": True,
        "CellsNetsAndConnectionsUnchanged": True, "ActualInputFileModified": False,
    }
    result["CheckerSHA256"] = sha(entry.__file__)
    return result


def audit_vendor_sources(project=PROJECT, vendor=VENDOR):
    project, vendor = Path(project).resolve(), Path(vendor).resolve()
    roles = candidate.validate(project)
    prefix = candidate.paths.IP + "/"
    names = [candidate.paths.IDF, *roles["IDFExpandedSources"]]
    require(len(names) == 75 and len(set(names)) == 75, "one IDF and 74 bodies required")
    records = []
    for name in names:
        require(name.startswith(prefix), "IP body outside expected candidate directory")
        relative = name[len(prefix):]
        current, reference = project / name, vendor / relative
        require(reference.is_file() and reference.resolve().is_relative_to(vendor),
                "vendor reference is missing or escaped its directory: " + relative)
        digest = sha(current)
        require(digest == roles["SourceSHA256"][name] == sha(reference),
                "current/manifest/vendor bytes differ: " + relative)
        records.append({"CandidatePath": str(current), "VendorPath": str(reference),
                        "RelativePath": relative, "SHA256": digest})
    fdc = vendor / "pnr/ddr_test.fdc"
    fdc_text = fdc.read_text(encoding="utf-8-sig")
    relationships = []
    for name in ("rst_clk", "phy_dq_clk_0", "phy_dq_clk_1"):
        expected = (f"set_clock_groups -name {name} -asynchronous "
                    f"-group [get_clocks {{{name}}}]")
        lines = [i for i, line in enumerate(fdc_text.splitlines(), 1) if line.strip() == expected]
        require(len(lines) == 1, "required vendor asynchronous relationship differs: " + name)
        relationships.append({"Clock": name, "Line": lines[0], "Command": expected})
    for record in records:
        require(sha(record["CandidatePath"]) == sha(record["VendorPath"]) == record["SHA256"],
                "source changed during read-only audit")
    return {"Status": "pass", "CandidateManifest": str(project / candidate.MANIFEST),
            "CandidateManifestSHA256": sha(project / candidate.MANIFEST),
            "IDFAndExpandedBodyCount": len(records), "AllBytesIdentical": True,
            "Files": records, "VendorFDC": {"Path": str(fdc), "SHA256": sha(fdc)},
            "OriginalVendorAsynchronousRelationships": relationships,
            "GlobalClockGroupsImported": False, "ConstraintsApplied": False,
            "Limit": "Same-config source/constraint provenance; actual endpoint scope is a separate audit."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists(), "output must be new")
    result = {"Schema": "processed-output-reset-evidence-v1", "Vendor": audit_vendor_sources(),
              "ConstraintsApplied": False, "HardwareAccessed": False,
              "HardwareReleaseAllowed": False, "TimingExceptionApproved": False,
              "AuditToolSHA256": sha(__file__)}
    if args.netlist:
        raw = args.netlist.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        result["Entry"] = audit_entry_text(raw.decode("utf-8-sig"))
        require(sha(args.netlist) == digest, "netlist changed during audit")
        result["InputNetlist"] = {"Path": str(args.netlist.resolve()), "Bytes": len(raw),
                                  "SHA256": digest}
        result["NativeExportProvenanceVerified"] = False
        result["ExportBindingRequirement"] = "Bind this netlist to the authority ADF and native export receipt separately."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"VendorSourceCount": result["Vendor"]["IDFAndExpandedBodyCount"],
                      "EntryStatus": result.get("Entry", {}).get("Status", "not_requested"),
                      "Output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
