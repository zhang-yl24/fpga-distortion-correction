"""Export a source-complete competition package from an immutable Git commit.

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
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


CURRENT_PACKAGE = "distortion/results/hdmi-camera-fisheye-tile8-20261103-a/"
DIRECT_PLAN = CURRENT_PACKAGE + "evidence/next-d/df8/files/0014/plan.json"
DIRECT_BIT = CURRENT_PACKAGE + "evidence/next-d/df8/files/0037/hdmi_camera_fisheye_top.sbit"
DIRECT_BIT_SHA = "aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b"
CODE_EXTENSIONS = {
    ".v", ".vh", ".vp", ".sv", ".svh", ".vhd", ".vhdl", ".py", ".pyi",
    ".tcl", ".pcf", ".fdc", ".rcf", ".idf", ".sdc", ".xdc", ".pdc",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".s", ".asm", ".ps1", ".psm1",
    ".sh", ".bat", ".cmd", ".m", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".jsx", ".html", ".css", ".xml", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".pds", ".f", ".qsf", ".qpf", ".prj", ".xpr", ".ipx",
    ".mem", ".hex", ".mif", ".coe", ".rom", ".lut",
}
ARCHIVES = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}
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
    """Return (include, auditable reason); preserve code before removing old data."""
    path = safe_relative(name)
    if any(p in PRIVATE_PARTS for p in path.parts):
        return False, "environment/cache metadata, not a project input"
    if name in protected:
        return True, "manifest-bound production input or released bitstream"
    if name.startswith(CURRENT_PACKAGE):
        return True, "complete current tile8/directfill A-B-C-D archive; preserve portable checks"
    if is_code(name):
        return True, "source/constraint/script/test fixture; retained regardless of historical location"
    if path.suffix.lower() in ARCHIVES:
        return False, "nested release archive; expanded project code retained separately"
    if name.startswith("vendor/"):
        return False, "historical vendor documents/data/build outputs; code and bound inputs retained"
    if name.startswith("distortion/captures/"):
        if path.suffix.lower() in {".json", ".csv", ".md", ".txt"}:
            return True, "capture/calibration metadata; bulk raw images omitted"
        return False, "historical raw capture data; current calibration retained in delivery"
    if name.startswith("distortion/results/"):
        if path.suffix.lower() == ".md":
            return True, "historical source context; full old measurement archive omitted"
        return False, "historical measurement/build data outside current release archive"
    if name.startswith("handoff/baseline/"):
        return False, "historical baseline measurement data; source retained"
    return True, "project source, delivery, tests, metadata, documentation or supporting fixture"


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


def bound_inputs(reader, entries):
    protected = {DIRECT_PLAN, DIRECT_BIT}
    hashes = {DIRECT_BIT: DIRECT_BIT_SHA}
    # This is the actual directfill production closure, not the old tile8 preset.
    plan = load_json(reader, entries, DIRECT_PLAN)
    require(len(plan["CompiledInputs"]) == 110, "Unexpected directfill closure size")
    require(not plan["SourceRoles"]["UnresolvedModuleInstances"], "Unresolved production modules")
    for item in plan["CompiledInputs"]:
        name = "distortion/" + item["Source"]
        protected.add(name)
        hashes[name] = item["OriginalSHA256"]
    manifest_name = "distortion/board/hdmi-camera-fisheye-tile8df8-build-sources.json"
    manifest = load_json(reader, entries, manifest_name)
    protected.add(manifest_name)
    protected.add("distortion/" + manifest["Constraint"])
    route = "distortion/" + manifest["RouteConstraint"]
    protected.add(route)
    hashes[route] = manifest["RouteConstraintSHA256"]
    # Preserve C/S3/tile8 portable source verification, including out-of-folder bits.
    for name in entries:
        if name.startswith("delivery/") and name.endswith("/source-manifest.json"):
            data = load_json(reader, entries, name)
            for item in data.get("Files", []):
                if isinstance(item, dict) and isinstance(item.get("Source"), str):
                    source = item["Source"]
                    if source in entries:
                        protected.add(source)
            bit = data.get("ReleasedBitstream", {})
            if isinstance(bit, dict) and bit.get("RepositoryPath"):
                source = bit["RepositoryPath"]
                require(source in entries, "Released bitstream missing: " + source)
                protected.add(source)
    require(protected <= entries.keys(), "Bound production input missing from Git tree")
    return protected, hashes


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
 'source_commit':manifest['SourceCommit'],'current_bit':manifest['DirectfillBitstreamSHA256']},indent=2))
'''


def startup(commit):
    return f'''# 竞赛代码包入口

本包从 Git 提交 `{commit}` 的原始 blob 导出，不含 Git 历史，不改写冻结源码或证据。
本包选定版本为 directfill INDEX8 v3，位流 SHA256：`{DIRECT_BIT_SHA}`。
此版本约 15 个新校正显示帧/秒、约 30 Hz 扫描；不是 30 个新校正帧/秒。

## 先校验

在解压根目录运行（Python 3.10+，均不访问硬件）：

```text
python -B VERIFY_SUBMISSION.py
python -B delivery/20261103-hdmi-camera-fisheye-tile8/verify_source.py
python -B delivery/20261103-hdmi-camera-fisheye-fill8/verify_source.py
python -B delivery/20261103-hdmi-camera-fisheye-c/verify_source.py
python -B distortion/results/hdmi-camera-fisheye-tile8-20261103-a/verify_archive_portable.py --manifest portable-evidence-manifest-c.json
python -B delivery/20261104-hdmi-camera-fisheye-tile8-directfill/verify_stage_d_portable.py --package distortion/results/hdmi-camera-fisheye-tile8-20261103-a
```

上面的校验使用各交付目录的独立脚本，重放保存的身份与数据；不重新执行 EDA、仿真、烧录
或板测。PR #28 的统一入口和新增实验聚合已按要求撤回，本包不依赖该入口或版本目录表，
不重新收录此次撤回的实验目录。完整原仓库与历史数据仍以项目 GitHub 为准。

Windows 包内部分历史路径超过 260 字符，导出与 SHA 验证器已自动兼容。
执行交付校验脚本时可在 PowerShell 使用扩展路径入口（内容不变）：

```powershell
$taskPrefix = [string][char]92 + [char]92 + '?' + [char]92
$taskEntry = $taskPrefix + (Resolve-Path ./delivery/20261104-hdmi-camera-fisheye-tile8-directfill/verify_stage_d_portable.py).Path
$taskPackage = $taskPrefix + (Resolve-Path ./distortion/results/hdmi-camera-fisheye-tile8-20261103-a).Path
python -B $taskEntry --package $taskPackage
```

其余脚本同样使用扩展绝对路径。解压与构建目录仍建议使用短路径。

## 当前版本与构建边界

- 版本说明：`delivery/20261104-hdmi-camera-fisheye-tile8-directfill/README.md`。
- 当前实际 bit：`{DIRECT_BIT}`；下载前校验 SHA256，SRAM 与 Flash 操作应明确区分。
- 110 项生产输入：`distortion/board/hdmi-camera-fisheye-tile8df8-build-sources.json`。
- 绑定的实际构建计划：`{DIRECT_PLAN}`；原始 Tcl 在同一 `files/0409/build.tcl`。
- 6 份当时编译快照在 `files/0194`、`0195`、`0204`、`0287`、`0290`、`0291`，
  保留原 include 重定位和顶层 `INPUT_TIMING_CONFIGURED=1`。它们属于当前位流的源证据。
- 旧 `delivery/20261103-hdmi-camera-fisheye-tile8/prepare_build.py` 准备的是旧 tile8，
  **不是 directfill 一键重建工具**。本代码包不假装提供当前 directfill 的一键 EDA 重建。
  对 directfill 重建须按实际清单重定位冻结 include/Tcl，并重新完成物理及板测验证。
- PDS 程序、许可证、安装目录中的器件原语库和模拟器不随包提供；使用相容的合法安装。
  当前归档使用 PDS 2023.2-SP3 build 154097；已入库 DDR IDF、74 项展开源、PLL/板级控制
  和相应约束均保留原字节与来源，不由本包重新授权。
- 标定：`delivery/20261103-hdmi-camera-fisheye-c/calibration/`；部署参数头与径向 ROM
  在 `distortion/board/hdmi-camera-fisheye-profile.vh`、`hdmi-camera-fisheye-radial-table.vh`。

## 包含和裁剪范围

所有 tracked 作者源代码、脚本、约束、测试及常见向量文件保留；必要平台 IP 保留。
当前 tile8/directfill A/B/C/D 结果包完整保留，使其 portable verifier 可执行。
源提交实际保留的 delivery 展开目录及参数保留；嵌套 ZIP/RAR 不重复打包。
旧 results 非代码数据、原始 capture 图像、vendor 参考资料/历史构建数据及缓存被裁剪，
逐项路径、Git blob、字节数、原因和是否为代码见 `SUBMISSION_EXCLUDED_FILES.json`。
故依赖这些旧测量目录的历史全仓测试可能需要原 GitHub 数据；本包不宣称重跑全部历史回归。

`SUBMISSION_MANIFEST.json` 记录 included 文件 SHA256、原提交/树和生产闭包检查。
它不包含自身哈希；最终 RAR 的 SHA256 与压缩后小于 200 MB 的检查在外部单独完成。
'''


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
                   "IncludedTrackedFiles": len(selected), "ExcludedFiles": len(omitted),
                   "IncludedBytes": sum(e["Bytes"] for e in selected),
                   "ExcludedCodeFiles": sum(e["CodeOrFixture"] for e in omitted),
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
            target = destination_root.joinpath(*safe_relative(entry["Path"]).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(data)
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
        manifest = dict(summary, Schema="competition-source-package-v1", IncludedFiles=written,
                        ExportedUTC=datetime.now(timezone.utc).isoformat(),
                        DirectfillBitstreamSHA256=DIRECT_BIT_SHA,
                        DirectfillProductionInputs=110, VerifiedExpectedHashes=verified_bound,
                        ProtectedTrackedFiles=len(protected), ManifestSelfExcluded=True,
                        CompressionPerformed=False, EDAExecuted=False, HardwareAccessed=False,
                        SizeBoundary="200 MB applies to final RAR; exporter reports uncompressed bytes")
        with (destination_root / "SUBMISSION_MANIFEST.json").open("xb") as handle:
            handle.write(json_bytes(manifest))
    subprocess.run([sys.executable, "-B", str(output / "VERIFY_SUBMISSION.py")], check=True)
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
