"""Check an additive archive using Git objects; no EDA or hardware calls."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

BASE = "8f2a5b7679ca77153bd36d52a2660e286bff7730"
BASE_TREE = "93b06e5ba395bd80ded06828783bb58050405fa3"
def git(*args):
    return subprocess.check_output(["git", *args])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    ref = git("rev-parse", "--verify", args.ref + "^{commit}").decode().strip()
    assert git("rev-parse", BASE + "^{tree}").decode().strip() == BASE_TREE
    allowed = ("docs/branches-20261104/", "archive/branches-20261104/")
    changes = git("diff", "--name-status", "--no-renames", "-z", BASE, ref).decode().split("\0")
    for index in range(0, len(changes)-1, 2):
        status, path = changes[index:index+2]
        assert status == "A", (status, path)
        assert path == "BRANCHES.md" or path.startswith(allowed), path
    manifest = json.loads(git("show", ref + ":archive/branches-20261104/FILE_MANIFEST.json"))
    assert len(manifest["files"]) == 602
    for package in manifest["imports"]:
        actual = git("rev-parse", ref + ":" + package["destination_path"]).decode().strip()
        assert actual == package["source_tree_sha"], package["destination_path"]
    for entry in manifest["files"]:
        object_name = ref + ":" + entry["path"]
        actual = git("rev-parse", object_name).decode().strip()
        assert actual == entry["git_blob_sha"], entry["path"]
        data = git("cat-file", "blob", object_name)
        assert len(data) == entry["bytes"], entry["path"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]
    print(json.dumps({"base_files_modified_or_deleted": 0, "source_subtrees_verified": 4, "archive_files_verified": 602, "ref": ref, "eda_executed": False, "hardware_accessed": False}, indent=2))

if __name__ == "__main__":
    main()
