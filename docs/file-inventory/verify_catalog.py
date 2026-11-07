#!/usr/bin/env python3
"""Validate the fixed-head inventory's integrity, not hardware correctness."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def require(condition, message):
    if not condition:
        raise SystemExit("FAIL: " + message)

def main():
    summary = json.loads((ROOT / "SUMMARY.json").read_text(encoding="utf-8"))
    raw = (ROOT / summary["csv"]["path"]).read_bytes()
    require(len(raw) == summary["csv"]["bytes"], "CSV byte count")
    require(hashlib.sha256(raw).hexdigest() == summary["csv"]["sha256"], "CSV SHA256")
    git_header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
    require(hashlib.sha1(git_header + raw).hexdigest() == summary["csv"]["git_blob_sha"], "Git blob SHA")
    require(b"\r" not in raw and raw.endswith(b"\n"), "LF and final newline")
    with (ROOT / summary["csv"]["path"]).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == summary["csv"]["columns"], "column order")
        rows = list(reader)
    require(len(rows) == summary["csv"]["data_rows"], "CSV data rows")
    known = {r["id"]: r for r in summary["per_ref"]}
    require(len(known) == summary["snapshot_count"], "snapshot IDs")
    memberships = defaultdict(list)
    blob_paths = defaultdict(set)
    blob_sizes = {}
    keys = set()
    logical = 0
    for row in rows:
        key = (row["path"], row["blob_sha"])
        require(key not in keys, "duplicate path/blob row")
        keys.add(key)
        size = int(row["size"])
        require(size >= 0, "nonnegative size")
        require(len(row["blob_sha"]) == 40 and all(c in "0123456789abcdef" for c in row["blob_sha"]), "blob SHA")
        require(row["path"] and not row["path"].startswith("/") and ".." not in row["path"].split("/"), "relative path")
        require(set(row["modes"].split(";")) <= {"100644", "100755", "120000"}, "blob modes")
        refs = row["ref_ids"].split(";")
        require(len(refs) == len(set(refs)) and set(refs) <= set(known), "ref membership")
        for ref in refs:
            memberships[ref].append(row)
        sha = row["blob_sha"]
        require(sha not in blob_sizes or blob_sizes[sha] == size, "consistent blob size")
        blob_sizes[sha] = size
        blob_paths[sha].add(row["path"])
        logical += size
    for row in rows:
        count = len(blob_paths[row["blob_sha"]])
        require(int(row["duplicate_path_count"]) == count, "duplicate path count")
        require(row["duplicate_group"] == (row["blob_sha"] if count > 1 else ""), "duplicate group")
    for ref, expected in known.items():
        selected = memberships[ref]
        require(len(selected) == expected["file_count"], ref + " file count")
        require(len({r["path"] for r in selected}) == len(selected), ref + " unique paths")
        require(sum(int(r["size"]) for r in selected) == expected["logical_bytes"], ref + " bytes")
        require(len({r["blob_sha"] for r in selected}) == expected["unique_blobs"], ref + " unique blobs")
        require(dict(Counter(r["category"] for r in selected)) == expected["category_counts"], ref + " categories")
    u = summary["union"]
    require(len(rows) == u["records"], "union records")
    require(len({r["path"] for r in rows}) == u["distinct_paths"], "union paths")
    require(len(blob_sizes) == u["distinct_blobs"], "union blobs")
    require(logical == u["path_blob_logical_bytes"], "union bytes")
    require(sum(blob_sizes.values()) == u["unique_blob_bytes"], "unique blob bytes")
    require(sum(len(paths) > 1 for paths in blob_paths.values()) == u["cross_path_duplicate_blob_groups"], "duplicate groups")
    require(sum(blob_sizes[sha] * (len(paths) - 1) for sha, paths in blob_paths.items()) == u["logical_repeated_path_bytes"], "duplicate logical bytes")
    print(f"PASS: {len(rows)} path/blob rows, {len(known)} complete fixed-head memberships, {len(blob_sizes)} blobs")

if __name__ == "__main__":
    main()
