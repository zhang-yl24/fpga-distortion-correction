"""Export two selected, source-complete implementations from a Git commit.

No checkout, compression, EDA, hardware access, or modification of frozen files.
Git blob bytes are exported directly so Windows checkout conversion cannot alter
bound sources. RAR creation and the 200 MB compressed-size check are separate.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


DIRECT_BIT_SHA = "aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b"
CAMERA720_PACKAGE = "distortion/results/camera720-view-toggle-live-20261102-a/"
CAMERA720_SUMMARY = CAMERA720_PACKAGE.rstrip("/") + ".json"
CAMERA720_BIT_GZ = CAMERA720_PACKAGE + "candidate/camera720_view_toggle_top.sbit.gz"
CAMERA720_BIT_SHA = "0ca6d19bf074c73cba0346a22e54ba3afb99a595728e6420a1cbb767b963dfe5"
CAMERA720_DELIVERY = "delivery/20261104-camera720p15/"
DIRECT_REPORTS = "delivery/20261104-hdmi-camera-fisheye-tile8-directfill/reports/"
DIRECT_SUBMISSION = "delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/"
SUPPORT_FILES = {
    "tools/package_submission.py", "tools/SUBMISSION_PACKAGE.md", "tools/tests/test_package_submission.py",
    "distortion/tools/calibrate_kb_tangential.py", "distortion/tools/compare_fisheye_projections.py",
    "requirements-team.txt", "handoff/CAMERA_720P_VIEW_TOGGLE_20261102.md",
}
CODE_EXTENSIONS = {
    ".v", ".vh", ".vp", ".sv", ".svh", ".vhd", ".vhdl", ".py", ".pyi",
    ".tcl", ".pcf", ".fdc", ".rcf", ".idf", ".sdc", ".xdc", ".pdc",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".s", ".asm", ".ps1", ".psm1",
    ".sh", ".bat", ".cmd", ".m", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".jsx", ".html", ".css", ".xml", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".pds", ".f", ".qsf", ".qpf", ".prj", ".xpr", ".ipx",
    ".mem", ".hex", ".mif", ".coe", ".rom", ".lut",
}
PRIVATE_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
GENERATED = {"SUBMISSION_MANIFEST.json", "SUBMISSION_EXCLUDED_FILES.json",
             "START_HERE_SUBMISSION.md", "VERIFY_SUBMISSION.py"}


def require(value, message):
    if not value:
        raise ValueError(message)


def filesystem_path(path):
    """Use extended Windows paths without changing package-relative identities."""
    path = Path(path).absolute()
    if os.name == "nt" and not str(path).startswith("\\\\?\\"):
        value = str(path)
        return Path("\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value)
    return path


def safe_relative(name):
    path = PurePosixPath(name)
    require(bool(name) and not path.is_absolute() and ".." not in path.parts
            and ":" not in name and "\\" not in name
            and not any(ord(c) < 32 for c in name), "Unsafe Git path: " + repr(name))
    return path


def is_code(name):
    path = PurePosixPath(name)
    return path.suffix.lower() in CODE_EXTENSIONS or path.name.lower() in {
        "makefile", "cmakelists.txt", "dockerfile", "requirements.txt", "requirements-dev.txt"
    }


def select_file(name, protected=frozenset()):
    """Two selected implementations only; record removal of other-route code."""
    path = safe_relative(name)
    if any(p in PRIVATE_PARTS for p in path.parts):
        return False, "environment/cache metadata, not a project input"
    if name in protected:
        return True, "manifest-bound input of the selected 720p15/1080p15 implementations"
    if name.startswith(CAMERA720_PACKAGE) or name == CAMERA720_SUMMARY:
        return True, "complete primary 720p15 view-toggle archive and summary, including compressed bit/evidence"
    if name.startswith((CAMERA720_DELIVERY, DIRECT_SUBMISSION, DIRECT_REPORTS)):
        return True, "primary version frozen sources/reports, including original gzip timing reports"
    if name.startswith("submission/") or name in SUPPORT_FILES:
        return True, "competition report, parameters, selected-version notes or packaging/report support"
    if is_code(name):
        return False, "other-route/historical code outside the two selected source closures; repository unchanged"
    return False, "other-route delivery, data, bitstream or repository history outside the selected scope"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def tree_entries(repo, commit):
    result = []
    for raw in git(repo, "ls-tree", "-rlz", commit).split(b"\0"):
        if not raw:
            continue
        meta, rawname = raw.split(b"\t", 1)
        mode, kind, oid, size = meta.split()
        name = rawname.decode("utf-8")
        safe_relative(name)
        require(kind == b"blob" and mode in (b"100644", b"100755"),
                "Submodule/symlink/non-file needs explicit packaging policy: " + name)
        require(name not in GENERATED, "Generated package filename conflicts with tracked file: " + name)
        result.append({"Path": name, "Bytes": int(size), "GitBlob": oid.decode(), "GitMode": mode.decode()})
    return result


class BlobReader:
    def __init__(self, repo):
        self.process = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read(self, oid):
        self.process.stdin.write((oid + "\n").encode("ascii"))
        self.process.stdin.flush()
        header = self.process.stdout.readline().split()
        require(len(header) == 3 and header[1] == b"blob", "Git object is unavailable: " + oid)
        remaining = int(header[2])
        chunks = []
        while remaining:
            block = self.process.stdout.read(min(remaining, 1024 * 1024))
            require(block, "Truncated Git object: " + oid)
            chunks.append(block)
            remaining -= len(block)
        require(self.process.stdout.read(1) == b"\n", "Bad Git batch framing")
        return b"".join(chunks)

    def close(self):
        self.process.stdin.close()
        self.process.stdout.close()
        require(self.process.wait() == 0, "git cat-file failed")


@contextmanager
def blobs(repo):
    reader = BlobReader(repo)
    try:
        yield reader
    finally:
        reader.close()


def load_json(reader, entries, name):
    require(name in entries, "Required tracked input missing: " + name)
    return json.loads(reader.read(entries[name]["GitBlob"]))


def bound_manifest(reader, entries, name, schema, protected, hashes, minimum=0):
    data = load_json(reader, entries, name)
    require(data.get("schema", data.get("Schema")) == schema, "Unexpected source manifest schema: " + name)
    require(len(data["files"]) >= minimum, "Incomplete selected source closure: " + name)
    protected.add(name)
    folder = PurePosixPath(name).parent
    seen = set()
    for item in data["files"]:
        relative = safe_relative(item["path"])
        source = (folder / relative).as_posix()
        require(source not in seen, "Duplicate selected source: " + source)
        seen.add(source)
        require(source in entries, "Missing selected source: " + source)
        require(entries[source]["Bytes"] == item["bytes"], "Selected source size differs: " + source)
        require(len(item["sha256"]) == 64 and all(c in "0123456789abcdef" for c in item["sha256"]),
                "Invalid selected source SHA256: " + source)
        protected.add(source)
        hashes[source] = item["sha256"]
    return data


def bound_inputs(reader, entries):
    protected, hashes = set(), {}
    camera_manifest_name = CAMERA720_PACKAGE + "manifest.json"
    camera_manifest = load_json(reader, entries, camera_manifest_name)
    camera_summary = load_json(reader, entries, CAMERA720_SUMMARY)
    require(camera_manifest["Schema"] == "camera720-view-toggle-evidence-manifest-v1",
            "Unexpected 720p archive manifest")
    require(camera_summary["Bitstream"]["SHA256"] == CAMERA720_BIT_SHA,
            "720p summary bitstream identity differs")
    protected.update({camera_manifest_name, CAMERA720_SUMMARY})
    hashes[camera_manifest_name] = camera_summary["EvidenceManifest"]["SHA256"]
    stored_names = set()
    for row in camera_manifest["Files"]:
        safe_relative(row["File"])
        name = CAMERA720_PACKAGE + row["File"]
        require(name not in stored_names, "Duplicate 720p archive member: " + name)
        stored_names.add(name)
        protected.add(name)
        hashes[name] = row["SHA256"]
    require(CAMERA720_BIT_GZ in stored_names, "720p released gzip bitstream is missing")
    bound_manifest(reader, entries, CAMERA720_DELIVERY + "source-manifest.json",
                   "camera720p15-frozen-source-closure-v1", protected, hashes, 118)
    bound_manifest(reader, entries, CAMERA720_DELIVERY + "reports-manifest.json",
                   "camera720p15-native-reports-v1", protected, hashes)
    direct = bound_manifest(reader, entries, DIRECT_SUBMISSION + "source-manifest.json",
                           "tile8-directfill-selected-submission-v1", protected, hashes, 110)
    seen = set()
    for item in direct.get("report_files", []):
        source = DIRECT_REPORTS + safe_relative(item["path"]).as_posix()
        require(source not in seen and source in entries, "Missing/duplicate selected report: " + source)
        seen.add(source)
        require(entries[source]["Bytes"] == item["bytes"], "Selected report size differs: " + source)
        protected.add(source)
        hashes[source] = item["sha256"]
    identity = load_json(reader, entries, CAMERA720_DELIVERY + "identity.json")
    camera_bit = CAMERA720_DELIVERY + safe_relative(identity["bitstream"]["path"]).as_posix()
    protected.add(camera_bit)
    hashes[camera_bit] = CAMERA720_BIT_SHA
    require(protected <= entries.keys(), "Selected production input missing from Git tree")
    return protected, hashes


def check_bitstream(name, data):
    """Reject other executable bitstreams, even inside selected directories."""
    lower = name.lower()
    if not lower.endswith((".sbit", ".bit", ".sbit.gz", ".bit.gz")):
        return
    raw = gzip.decompress(data) if lower.endswith(".gz") else data
    expected = (CAMERA720_BIT_SHA if name.startswith((CAMERA720_PACKAGE, CAMERA720_DELIVERY))
                else DIRECT_BIT_SHA if name.startswith(DIRECT_SUBMISSION) else None)
    require(expected is not None, "Bitstream outside selected delivery: " + name)
    require(hashlib.sha256(raw).hexdigest() == expected, "Unselected bitstream identity: " + name)


def verify_selected_export(output):
    root = filesystem_path(output)
    for script, arguments in (
        ("VERIFY_SUBMISSION.py", []),
        (CAMERA720_DELIVERY + "verify_selected.py", []),
        (CAMERA720_PACKAGE + "verify_bundle.py", ["--summary", str(root / CAMERA720_SUMMARY)]),
        (DIRECT_SUBMISSION + "verify_selected.py", []),
    ):
        subprocess.run([sys.executable, "-I", "-B", str(root / script), *arguments], check=True)


VERIFY_SCRIPT = '''"""Read-only package SHA256 check; no Git or third-party modules required."""
import hashlib,json,os
from pathlib import Path,PurePosixPath
root=Path(__file__).resolve().parent
if os.name=='nt' and not str(root).startswith(chr(92)*2+'?'+chr(92)):
    value=str(root)
    root=Path(chr(92)*2+'?'+chr(92)+('UNC'+chr(92)+value[2:] if value.startswith(chr(92)*2) else value))
manifest=json.loads((root/'SUBMISSION_MANIFEST.json').read_text(encoding='utf-8'))
for entry in manifest['IncludedFiles']:
    relative=PurePosixPath(entry['Path'])
    if relative.is_absolute() or '..' in relative.parts or ':' in entry['Path'] or '\\\\' in entry['Path']:
        raise SystemExit('Unsafe path: '+entry['Path'])
    path=root.joinpath(*relative.parts)
    if not path.is_file() or path.stat().st_size!=entry['Bytes']:
        raise SystemExit('Missing or size mismatch: '+entry['Path'])
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=entry['SHA256']:
        raise SystemExit('SHA256 mismatch: '+entry['Path'])
print(json.dumps({'verified':True,'files':len(manifest['IncludedFiles']),
 'source_commit':manifest['SourceCommit'],'directfill_bit':manifest['DirectfillBitstreamSHA256'],
 'camera720_bit':manifest.get('Camera720BitstreamSHA256')},indent=2))
'''


def startup(commit):
    return f"""# 竞赛提交：两套选定版本

本包从提交 `{commit}` 的原始 Git blob 导出，只提供以下两套选定工程、各自原生报告和提交材料。
仓库其余版本保留在 Git 历史中，未重新放入本 RAR。本轮导出及校验不访问硬件。

| 选定工程 | 已记录的新校正显示帧率 | 位流 SHA256 |
| --- | --- | --- |
| OV5640 1280×720 原图/校正切换 | 15 FPS | `{CAMERA720_BIT_SHA}` |
| HDMI 1920×1080 directfill INDEX8 v3 | 15 FPS | `{DIRECT_BIT_SHA}` |

1080p 约30 Hz扫描包含重复显示，不等于30个新校正帧/秒。两版接口、镜头参数、顶层与位流分别绑定。

## 两套入口

- [720p15 源码、解压位流及报告](delivery/20261104-camera720p15/README.md)。
- [1080p15 选定源码、唯一位流及证据](delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md)。
- [报告、海报及参数资料](submission/README.md)。

每套工程的源清单逐项绑定文件字节和 SHA256。720p 冻结构建输入、1080p 的110项生产输入、
RCF和编译差异均由对应清单保护；原始 STA gzip 和资源证据保留，不能用不同位流的数据互换。
旧 fisheye C、S3、旧tile8、throughput、stable30等交付不属于本包的可选下载版本。

## 在解压目录校验

Python 3.10+，只用标准库，无需 Git、PDS 或板卡：

```text
python -B VERIFY_SUBMISSION.py
python -B delivery/20261104-camera720p15/verify_selected.py
python -B distortion/results/camera720-view-toggle-live-20261102-a/verify_bundle.py --summary distortion/results/camera720-view-toggle-live-20261102-a.json
python -B delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/verify_selected.py
```

这些命令核对保存的源码、报告、位流及板测记录；不重跑EDA、HDL或板测。旧1080p C/D整包
校验器需要完整历史归档，不是此精选包的校验入口，也不宣称其在此包可运行。

Windows 深层冻结路径可能超过260字符。总SHA校验器自动兼容；原有归档脚本可这样启动：

```powershell
$taskPrefix = [string][char]92 + [char]92 + '?' + [char]92
$taskScript = $taskPrefix + (Resolve-Path ./distortion/results/camera720-view-toggle-live-20261102-a/verify_bundle.py).Path
$taskSummary = $taskPrefix + (Resolve-Path ./distortion/results/camera720-view-toggle-live-20261102-a.json).Path
python -B $taskScript --summary $taskSummary
```

## 720p原gzip位流

720p独立交付提供解压位流。原206项封存证据也保留在 `{CAMERA720_PACKAGE}`；
其中 `{CAMERA720_BIT_GZ}` 是压缩存储，不能直接把.gz文件用于下载。
如需另行解压，在包根执行下列Python代码，输出必须不存在：

```python
import gzip, hashlib
from pathlib import Path
source = Path("{CAMERA720_BIT_GZ}")
data = gzip.decompress(source.read_bytes())
assert hashlib.sha256(data).hexdigest() == "{CAMERA720_BIT_SHA}"
with Path("camera720_view_toggle_top.sbit").open("xb") as output:
    output.write(data)
```

## 源码重建与材料边界

两套源包保留真实编译输入和原构建说明，不承诺重新布线得到相同bit。历史生成脚本可能仍
引用原工作区，应按各自源清单重定位后构建，并重新完成时序、接口及板测验证。
厂商PDS安装、许可证、安装目录中的原语库与模拟器不随包提供；使用相容合法工具。
原归档对应PDS 2023.2-SP3 build154097。已有DDR/PLL/IP输入保留原字节和来源。

`submission/` 中标定扩展、投影比较等材料是报告的离线补充，不是第三套FPGA部署版本，
不改变这两套位流。完整原始采图不随报告补充数据发布。

## 文件审计与压缩

`SUBMISSION_MANIFEST.json` 绑定所有included文件SHA、原提交与树；自身哈希不递归收录。
`SUBMISSION_EXCLUDED_FILES.json` 逐项记录旧路线代码、数据、旧位流和非必要支持文件的裁剪原因。
`ExcludedCodeFiles` 统计的是有记录裁剪的其他路线/历史代码，不表示所选两套源闭包缺失，
也不宣称本包包含整个仓库的全部历史实验。仓库本身未因打包被删除文件。

最终RAR需另做压缩完整性测试、解压后上述校验，且严格小于200,000,000字节。
"""


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def export(repo, ref, output, plan_only=False):
    repo = Path(repo).resolve()
    output = Path(output).resolve()
    require(not output.exists(), "Output already exists; choose a fresh directory")
    commit = git(repo, "rev-parse", "--verify", ref + "^{commit}").decode().strip()
    tree = git(repo, "rev-parse", commit + "^{tree}").decode().strip()
    entries = {x["Path"]: x for x in tree_entries(repo, commit)}
    with blobs(repo) as reader:
        protected, expected = bound_inputs(reader, entries)
        selected, omitted = [], []
        for name, entry in entries.items():
            keep, reason = select_file(name, protected)
            item = dict(entry, Reason=reason, CodeOrFixture=is_code(name))
            (selected if keep else omitted).append(item)
        summary = {"SourceCommit": commit, "SourceTree": tree, "TrackedFiles": len(entries),
                   "Scope": "two-selected-implementations-720p15-and-1080p15",
                   "IncludedTrackedFiles": len(selected), "ExcludedFiles": len(omitted),
                   "IncludedBytes": sum(e["Bytes"] for e in selected),
                   "ExcludedCodeFiles": sum(e["CodeOrFixture"] for e in omitted),
                   "ExcludedCodeMeaning": "audited other-route/history/support code outside selected source closures",
                   "ExcludedReasons": dict(Counter(e["Reason"] for e in omitted))}
        if plan_only:
            return summary
        destination_root = filesystem_path(output)
        destination_root.mkdir(parents=True, exist_ok=False)
        written = []
        verified_bound = 0
        for entry in selected:
            data = reader.read(entry["GitBlob"])
            require(len(data) == entry["Bytes"], "Git size mismatch: " + entry["Path"])
            digest = hashlib.sha256(data).hexdigest()
            if entry["Path"] in expected:
                require(digest == expected[entry["Path"]], "Production SHA mismatch: " + entry["Path"])
                verified_bound += 1
            check_bitstream(entry["Path"], data)
            target = destination_root.joinpath(*safe_relative(entry["Path"]).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(data)
            require(hashlib.sha256(target.read_bytes()).hexdigest() == digest,
                    "Copied byte SHA mismatch: " + entry["Path"])
            written.append(dict(entry, SHA256=digest))
        excluded_report = {"Schema": "competition-source-exclusions-v1", "SourceCommit": commit,
                           "ExcludedFiles": omitted}
        generated = {"SUBMISSION_EXCLUDED_FILES.json": json_bytes(excluded_report),
                     "START_HERE_SUBMISSION.md": startup(commit).encode("utf-8"),
                     "VERIFY_SUBMISSION.py": VERIFY_SCRIPT.encode("utf-8")}
        for name, data in generated.items():
            with (destination_root / name).open("xb") as handle:
                handle.write(data)
            written.append({"Path": name, "Bytes": len(data), "SHA256": hashlib.sha256(data).hexdigest(),
                            "Reason": "generated package metadata or read-only verifier", "Generated": True})
        manifest = dict(summary, Schema="competition-two-selected-source-package-v2", IncludedFiles=written,
                        ExportedUTC=datetime.now(timezone.utc).isoformat(),
                        DirectfillBitstreamSHA256=DIRECT_BIT_SHA,
                        Camera720BitstreamSHA256=CAMERA720_BIT_SHA,
                        Camera720Archive=CAMERA720_PACKAGE, Camera720Summary=CAMERA720_SUMMARY,
                        DirectfillProductionInputs=110, VerifiedExpectedHashes=verified_bound,
                        ProtectedTrackedFiles=len(protected), ManifestSelfExcluded=True,
                        CompressionPerformed=False, EDAExecuted=False, HardwareAccessed=False,
                        SizeBoundary="200 MB applies to final RAR; exporter reports uncompressed bytes")
        with (destination_root / "SUBMISSION_MANIFEST.json").open("xb") as handle:
            handle.write(json_bytes(manifest))
    verify_selected_export(output)
    summary["Output"] = str(output)
    summary["TotalPackageBytes"] = sum(p.stat().st_size for p in destination_root.rglob("*") if p.is_file())
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ref", default="HEAD", help="immutable source commit or ref; working tree is not exported")
    parser.add_argument("--output", type=Path, required=True, help="new destination; existing directory is refused")
    parser.add_argument("--plan-only", action="store_true", help="print selection and sizes without writing files")
    args = parser.parse_args()
    print(json.dumps(export(args.repo, args.ref, args.output, args.plan_only), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
