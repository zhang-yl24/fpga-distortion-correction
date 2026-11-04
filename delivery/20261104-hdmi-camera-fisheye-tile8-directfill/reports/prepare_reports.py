"""Materialize a readable, byte-preserving report set from frozen stage D identities.

No build, audit, Git operation or hardware access. Run from any directory.
"""
from pathlib import Path
import gzip
import hashlib
import json
import re
import shutil

OUT = Path(__file__).resolve().parent
SUBMIT = OUT.parents[2]
PACKAGE = SUBMIT / 'distortion/results/hdmi-camera-fisheye-tile8-20261103-a'
MANIFEST = PACKAGE / 'portable-evidence-manifest-d.json'
manifest = json.loads(MANIFEST.read_bytes())
bundled = {v['Path']: v for v in manifest['BundledFiles']}

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def check(path, expected):
    actual = digest(path)
    assert actual == expected, (str(path), actual, expected)
    return actual

copies = []
def frozen_copy(relative, destination, purpose):
    src = PACKAGE / relative
    entry = bundled[relative]
    check(src, entry['SHA256'])
    dst = OUT / destination
    shutil.copyfile(src, dst)
    check(dst, entry['SHA256'])
    assert dst.stat().st_size == src.stat().st_size
    copies.append({'file': destination, 'purpose': purpose,
                   'source_archive_path': src.relative_to(SUBMIT).as_posix(),
                   'source_sha256': entry['SHA256'], 'copied_sha256': entry['SHA256'],
                   'bytes': dst.stat().st_size, 'copy_mode': 'byte-identical'})
    return dst

base = 'evidence/next-d/df8/files/'
resources = frozen_copy(base + '0011/df8-v3-final-resources-a.json',
                        'resource-binding.json', 'Final routed resources bound to actual SRAM bit')
resource = json.loads(resources.read_bytes())
chain = resource['EvidenceChain']
assert resource['FinalAttributionPassed'] and resource['OnBoardResourceBinding']
bit = PACKAGE / (base + '0037/hdmi_camera_fisheye_top.sbit')
check(bit, chain['Bitstream']['SHA256'])
assert chain['Bitstream']['SHA256'] == 'aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b'
assert chain['FinalADF']['SHA256'] == '2b6e662fb25cfb774a494743947c80325fd4796b423b3e0756a0f877117ae430'

for relative, destination, key, purpose in [
    ('0420/run_route_optimize.log', 'final_route_optimize.log', 'RouteOptimizeLog', 'Authoritative completed Route Optimize utilization table'),
    ('0490/hdmi_camera_fisheye_top_prr_route_optimize.prt', 'final_route_optimize_pins.prt', 'RouteOptimizePinReport', 'Completed Route Optimize physical pin report'),
]:
    dst = frozen_copy(base + relative, destination, purpose)
    check(dst, chain[key]['SHA256'])

verified = frozen_copy(base + '0003/verification.json', 'bit-verification.json', 'Saved final bit-generation verification and fresh STA identity')
preaudit = frozen_copy(base + '0006/pre-bit-audit.json', 'pre-bit-audit.json', 'Saved runtime pre-bit STA check')
v = json.loads(verified.read_bytes())
p = json.loads(preaudit.read_bytes())
assert v['Verified'] and v['FreshSTA']['STAAllTenPassed'] and p['GatePassed']
assert v['Bitstream']['SHA256'] == chain['Bitstream']['SHA256']
assert v['FinalADFSHA256'] == p['FinalADFSHA256'] == chain['FinalADF']['SHA256']

timing = next(x for x in manifest['ExternalPhysicalEvidence']
              if x['Path'].replace('\\', '/').endswith('bit-v3-a/report_timing/hdmi_camera_fisheye_top.rtr'))
timing_path = Path(timing['Path'])
assert timing['SHA256'] == v['EvidenceSHA256']['report_timing/hdmi_camera_fisheye_top.rtr']
assert timing['SHA256'] == p['EvidenceSHA256']['report_timing/hdmi_camera_fisheye_top.rtr']
check(timing_path, timing['SHA256'])
assert timing_path.stat().st_size == timing['Bytes']

# Take the exact leading bytes through all ten complete summary tables.
prefix = []
tables = []
active = None
with timing_path.open('rb') as f:
    for raw in f:
        line = raw.decode('utf8', errors='strict').strip()
        prefix.append(raw)
        match = re.fullmatch(r'(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):', line)
        if match:
            active = {'kind': match[1], 'corner': match[2], 'rows': []}
        elif active and re.fullmatch(r'=+', line):
            assert active['rows']
            values = active.pop('rows')
            active.update({'worst_slack_ns': min(x[0] for x in values),
                           'total_negative_slack_ns': sum(x[1] for x in values),
                           'failing_endpoints': sum(x[2] for x in values),
                           'total_endpoints': sum(x[3] for x in values)})
            tables.append(active)
            active = None
            if len(tables) == 10:
                break
        elif active:
            fields = line.split()
            try:
                row = (float(fields[-4]), float(fields[-3]), int(fields[-2]), int(fields[-1]))
            except (ValueError, IndexError):
                continue
            active['rows'].append(row)
assert len(tables) == 10
assert all(t['failing_endpoints'] == 0 and t['total_negative_slack_ns'] == 0 for t in tables)
summary = OUT / 'final_timing_summary.rtr'
summary.write_bytes(b''.join(prefix))
assert timing_path.open('rb').read(summary.stat().st_size) == summary.read_bytes()

# Gzip is only a lossless transport container; the uncompressed report is unchanged.
compressed = OUT / 'final_timing_full.rtr.gz'
with compressed.open('wb') as dst, gzip.GzipFile(filename='', mode='wb', fileobj=dst, mtime=0, compresslevel=6) as gz, timing_path.open('rb') as src:
    shutil.copyfileobj(src, gz, length=1024 * 1024)
decoded_sha = hashlib.sha256()
decoded_size = 0
with gzip.open(compressed, 'rb') as f:
    for block in iter(lambda: f.read(1024 * 1024), b''):
        decoded_sha.update(block)
        decoded_size += len(block)
assert decoded_sha.hexdigest() == timing['SHA256'] and decoded_size == timing['Bytes']

proof = next(x for x in manifest['ExternalPhysicalEvidence'] if x['SHA256'] == chain['FinalPhysicalProof']['SHA256'])
check(Path(proof['Path']), proof['SHA256'])
binding = {
    'schema': 'tile8-directfill-final-report-copies-v1',
    'frozen_source_commit': '45223998ce3695960297937519d37759499bb4f5',
    'variant': 'tile8 direct-fill INDEX8 v3 / 1080p15',
    'bitstream': {'archive_path': bit.relative_to(SUBMIT).as_posix(), 'sha256': digest(bit), 'bytes': bit.stat().st_size},
    'final_adf_sha256': chain['FinalADF']['SHA256'],
    'archive_manifest': {'path': MANIFEST.relative_to(SUBMIT).as_posix(), 'sha256': digest(MANIFEST)},
    'final_physical_proof': proof,
    'copied_reports': copies,
    'final_timing_report': {
        'source': timing,
        'stage': 'bit-v3-a fresh final audited ADF STA immediately before bit generation',
        'complete_report_file': compressed.name, 'gzip_sha256': digest(compressed), 'gzip_bytes': compressed.stat().st_size,
        'decoded_sha256': decoded_sha.hexdigest(), 'decoded_bytes': decoded_size,
        'summary_file': summary.name, 'summary_sha256': digest(summary), 'summary_bytes': summary.stat().st_size,
        'summary_original_lines': [1, len(prefix)], 'summary_is_complete_report': False,
        'summary_is_byte_identical_prefix': True, 'tables': tables,
    },
    'resources': resource['Resources'], 'io_used': chain['ActualPinCount'], 'io_capacity': 300,
    'resource_stage': chain['ResourceStage'],
    'resource_source_note': 'Route Optimize log is authoritative; earlier RUR and Map totals are not substituted.',
    'final_resource_binding': {
        'per_primitive_counts_equivalent': chain['PerPrimitiveCountsEquivalent'],
        'functional_graph_and_ff_placements_equal': chain['FunctionalGraphAndFFPlacementsIndependentlyEqual'],
        'route_trees_and_placements_equal': chain['RouteTreesAndPlacementsIndependentlyEqual'],
        'actual_program_device_and_done_checked': chain['ActualProgramDeviceAndPostProgramDONELogsChecked'],
    },
    'limits': {'external_ac_accepted': v['ExternalACAccepted'], 'pixels_verified_by_bit_verification': v['PixelsVerified'],
               'new_eda_executed': False, 'new_hardware_accessed': False, 'original_archive_files_modified': False},
}
(OUT / 'source-bindings.json').write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding='utf8')

readme = '''# 1080p15 direct-fill 最终时序与资源原始报告

本目录对应已板测的 **tile8 direct-fill INDEX8 v3**，完整1920×1080校正，约15个新帧/秒、30 Hz扫描。来源为提交 `4522399` 的阶段D冻结归档，未重新运行EDA或下载硬件。

位流SHA256：`aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b`。最终ADF：`2b6e662fb25cfb774a494743947c80325fd4796b423b3e0756a0f877117ae430`。

## 直接查看

| 文件 | 含义与阶段 |
| --- | --- |
| [final_timing_summary.rtr](final_timing_summary.rtr) | 原始最终时序报告的完整前部摘要，包含时钟与快慢双角十张表，保留原始字节。它是摘要截取，并非完整路径报告。 |
| [final_timing_full.rtr.gz](final_timing_full.rtr.gz) | 完整原始最终STA报告的无损gzip副本；解压后可查看所有详细路径。来自bit-v3-a，位流生成前针对audited-final.adf的实际STA。 |
| [final_route_optimize.log](final_route_optimize.log) | Route Optimize完成日志及Device Utilization Summary，资源总数采用此表。 |
| [final_route_optimize_pins.prt](final_route_optimize_pins.prt) | 同次Route Optimize引脚报告。 |
| [resource-binding.json](resource-binding.json) | 资源、原始日志、最终ADF、位流与SRAM下载身份的原始绑定回执。 |
| [bit-verification.json](bit-verification.json) · [pre-bit-audit.json](pre-bit-audit.json) | 位流生成与生成前时序核验原始回执。 |
| [source-bindings.json](source-bindings.json) | 每份副本的来源、大小、SHA256、gzip解压后SHA256和摘要范围。 |
| [verification.json](verification.json) | 独立PowerShell Get-FileHash与.NET GZipStream复核记录；生成脚本本身不代替此独立步骤。 |

## 最终结果

| 时序检查 | 慢角最差裕量 ns | 快角最差裕量 ns | 失败端点 |
| --- | ---: | ---: | ---: |
| Setup | +0.092 | +1.606 | 0 |
| Hold | +0.076 | +0.020 | 0 |
| Recovery | +1.019 | +2.184 | 0 |
| Removal | +0.257 | +0.030 | 0 |
| Minimum Pulse Width | +0.035 | +0.035 | 0 |

十张表的负裕量总和与失败端点均为零。上述值取各角相应表的全部行最小值；核心同域快角Setup为+2.917 ns，与快角全表最小值+1.606 ns口径不同。

| 资源 | 使用量／容量 | 精确计算后四舍五入占比 |
| --- | ---: | ---: |
| LUT | 13,875／66,600 | 20.83% |
| 逻辑FF | 14,397／133,200 | 10.81% |
| DRM 36K当量 | 43.5／155 | 28.06% |
| APM | 54／240 | 22.50% |
| IO | 144／300 | 48.00% |

LUT和FF分别合计Route Optimize表中的CLMA与CLMS行。DRM为42个36K及3个18K，折合43.5个36K。厂商原表百分比按整数显示，故可见DRM 29%、APM 23%；本表按使用量／容量计算，数值并不冲突。较早RUR可能先于最终CLM打包，不用它覆盖这里的最终优化资源。

## 冻结来源与核验

- [阶段D原始清单](../../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/portable-evidence-manifest-d.json)包含1593项归档文件及外部大报告的冻结哈希；本次未修改其中任何文件。
- [资源绑定原件](../../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/files/0011/df8-v3-final-resources-a.json)、[Route Optimize日志原件](../../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/files/0420/run_route_optimize.log)、[引脚报告原件](../../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/files/0490/hdmi_camera_fisheye_top_prr_route_optimize.prt)逐字复制。
- [正式位流原件](../../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/files/0037/hdmi_camera_fisheye_top.sbit)的SHA256与本目录绑定相同。
- 原始完整STA为840,398,885字节，SHA256 `404664d41d57f496ba0f58271977dc6c0048e4b36133cfa2ffcd0e77afe22c8f`；为便于提交压缩为gzip，解压后字节与哈希必须完全一致。gzip文件自身SHA256另列于source-bindings.json。
- `final_timing_summary.rtr`的原文行号范围、字节数和SHA256均列于source-bindings.json，可与解压后的完整报告前部直接比较。
- 原始资源绑定通过原生单元计数、功能连接、FF布局、布线路径及实际下载记录，将Route Optimize资源绑定到最终位流。本目录保留这些回执，没有将Map阶段结果当作最终布线资源。

以上是已采用约束下的内部实现检查，原始回执仍记录ExternalACAccepted=false；报告不将其改写为HDMI外部接口已完成独立AC签核。没有把时序裕量或处理时间倒数当作新校正帧率。
'''
(OUT / 'README.md').write_text(readme, encoding='utf8')
print(json.dumps({'reports': len(copies), 'timing_gzip_bytes': compressed.stat().st_size,
                  'summary_lines': len(prefix), 'decoded_sha256': decoded_sha.hexdigest(),
                  'sha256': digest(OUT / 'source-bindings.json'), 'tables': tables}, ensure_ascii=False, indent=2))
