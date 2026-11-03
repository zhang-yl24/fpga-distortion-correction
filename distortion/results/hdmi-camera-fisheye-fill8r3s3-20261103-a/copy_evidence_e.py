"""Copy only explicit, immutable evidence; never run providers, EDA or hardware."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import shutil

PACKAGE = Path(__file__).resolve().parent
REPOSITORY = PACKAGE.parents[2]
SCHEMA = "hdmi-camera-fisheye-fill8r3s3-approved-evidence-sources-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ref(path):
    return {"Path": str(path.resolve()), "SHA256": sha(path)}


def child(path, root):
    require(path == path.resolve() and path.is_relative_to(root), "noncanonical or escaped path: " + str(path))
    return path


def destination(relative):
    item = Path(relative)
    require(not item.is_absolute() and ".." not in item.parts and item.parts and
            (item.parts[0] == "evidence" or item.as_posix() == "artifacts/hdmi_camera_fisheye_top.sbit"),
            "only evidence/ or the explicitly approved selected sbit destination is accepted")
    return child((PACKAGE / item).absolute(), PACKAGE)


def inspect_source(row):
    source = child(Path(row["Source"]["Path"]).absolute(), REPOSITORY)
    require(source.is_file(), "missing source evidence: " + str(source))
    stat = source.stat()
    require(stat.st_size == row["Source"]["Bytes"] and sha(source) == row["Source"]["SHA256"],
            "approved source size/SHA drift: " + str(source))
    if row.get("JSONChecks"):
        value = json.loads(source.read_text(encoding="utf-8-sig"))
        for check in row["JSONChecks"]:
            current = value
            for key in check["Keys"]:
                current = current[key]
            require(current == check["Equals"], "completed evidence check failed: " + str(source) + " " + repr(check["Keys"]))
    require(row["Mode"] in ("copy", "reference"), "explicit copy/reference mode required")
    return source, stat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="approved-evidence-sources-e.json")
    parser.add_argument("--receipt", help="New package-relative receipt filename; never overwritten")
    parser.add_argument("--verify-only", action="store_true", help="Read-only verification of sources and archived copies")
    args = parser.parse_args()
    manifest_path = child((PACKAGE / args.sources).absolute(), PACKAGE)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    require(manifest["Schema"] == SCHEMA and manifest["ApprovedCompletedEvidenceOnly"] is True,
            "approved completed-evidence manifest required")
    entries = manifest["Entries"]
    require(entries and len({row["ID"] for row in entries}) == len(entries), "nonempty unique evidence inventory required")
    copy_paths = [row["Destination"] for row in entries if row["Mode"] == "copy"]
    require(len(copy_paths) == len(set(copy_paths)), "duplicate archive destination")
    if not args.verify_only:
        require(args.receipt, "a fresh receipt name is required for copying")
        receipt_path = child((PACKAGE / args.receipt).absolute(), PACKAGE)
        require(not receipt_path.exists() and receipt_path.parent == PACKAGE, "fresh package receipt required")
    manifest_ref = ref(manifest_path)
    inspected = [(row, *inspect_source(row)) for row in entries]
    for row, source, stat in inspected:
        if row["Mode"] != "copy":
            continue
        require(stat.st_size <= manifest["MaximumSingleCopyBytes"], "large evidence must be explicitly referenced or newly approved")
        target = destination(row["Destination"])
        if target.exists():
            require(target.is_file() and target.stat().st_size == stat.st_size and sha(target) == row["Source"]["SHA256"],
                    "existing archived evidence differs; it will not be overwritten")
        elif args.verify_only:
            raise ValueError("missing archived evidence: " + str(target))
    records = []
    for row, source, before in inspected:
        target = None
        copied = False
        if row["Mode"] == "copy":
            target = destination(row["Destination"])
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open("rb") as original, target.open("xb") as output:
                    shutil.copyfileobj(original, output, 8 * 1024 * 1024)
                os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
                copied = True
            require(sha(target) == row["Source"]["SHA256"], "archived copy SHA differs")
        after = source.stat()
        require(after.st_size == before.st_size and after.st_mtime_ns == before.st_mtime_ns and
                sha(source) == row["Source"]["SHA256"], "source evidence changed during archival")
        records.append({"ID": row["ID"], "Mode": row["Mode"], "Source": row["Source"],
                        "SourceMTimeNSBefore": before.st_mtime_ns, "SourceMTimeNSAfter": after.st_mtime_ns,
                        "Destination": str(target) if target else None,
                        "DestinationSHA256": sha(target) if target else None,
                        "CopiedThisRun": copied, "SourceBytesAndMTimeUnchanged": True})
    require(ref(manifest_path) == manifest_ref, "source inventory changed during archival")
    value = {"Schema": "hdmi-camera-fisheye-fill8r3s3-evidence-archive-receipt-v1", "Passed": True,
             "CheckedUTC": datetime.now(timezone.utc).isoformat(), "SourcesManifest": manifest_ref,
             "CopyTool": ref(Path(__file__).resolve()), "Entries": records,
             "CopiedEvidenceCount": len(copy_paths), "ReferenceOnlyCount": len(entries) - len(copy_paths),
             "CopiedThisRun": sum(row["CopiedThisRun"] for row in records),
             "SourceFilesModified": False, "Frozen77ManifestModified": False,
             "EDAExecuted": False, "HardwareAccessed": False, "ExternalPublicationPerformed": False,
             "CommitCreated": False, "ReleaseOrTimingAcceptanceConferred": False}
    if not args.verify_only:
        with receipt_path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
    print(json.dumps({"Passed": True, "VerifyOnly": args.verify_only,
                      "CopiedEvidenceCount": len(copy_paths), "ReferenceOnlyCount": len(entries) - len(copy_paths),
                      "CopiedThisRun": value["CopiedThisRun"],
                      "Receipt": str(receipt_path) if not args.verify_only else None}))


if __name__ == "__main__":
    main()
