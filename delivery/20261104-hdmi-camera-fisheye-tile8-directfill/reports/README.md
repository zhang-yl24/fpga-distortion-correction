# 1080p15 direct-fill 最终时序与资源原始报告

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
| [verification.json](verification.json) | 使用独立PowerShell Get-FileHash与.NET GZipStream复核全部原样副本和解压流SHA256，全部通过。 |

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

- [阶段D原始清单](https://github.com/zhang-yl24/fpga-distortion-correction/blob/45223998ce3695960297937519d37759499bb4f5/distortion/results/hdmi-camera-fisheye-tile8-20261103-a/portable-evidence-manifest-d.json)包含1593项归档文件及外部大报告的冻结哈希；本次未修改其中任何文件。
- [资源绑定原件](https://github.com/zhang-yl24/fpga-distortion-correction/blob/45223998ce3695960297937519d37759499bb4f5/distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/files/0011/df8-v3-final-resources-a.json)、[Route Optimize日志原件](https://github.com/zhang-yl24/fpga-distortion-correction/blob/45223998ce3695960297937519d37759499bb4f5/distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/files/0420/run_route_optimize.log)、[引脚报告原件](https://github.com/zhang-yl24/fpga-distortion-correction/blob/45223998ce3695960297937519d37759499bb4f5/distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/files/0490/hdmi_camera_fisheye_top_prr_route_optimize.prt)逐字复制。
- [正式位流原件](https://github.com/zhang-yl24/fpga-distortion-correction/blob/45223998ce3695960297937519d37759499bb4f5/distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/next-d/df8/files/0037/hdmi_camera_fisheye_top.sbit)的SHA256与本目录绑定相同。
- 原始完整STA为840,398,885字节，SHA256 `404664d41d57f496ba0f58271977dc6c0048e4b36133cfa2ffcd0e77afe22c8f`；为便于提交压缩为gzip，解压后字节与哈希必须完全一致。gzip文件自身SHA256另列于source-bindings.json。
- `final_timing_summary.rtr`的原文行号范围、字节数和SHA256均列于source-bindings.json，可与解压后的完整报告前部直接比较。
- 原始资源绑定通过原生单元计数、功能连接、FF布局、布线路径及实际下载记录，将Route Optimize资源绑定到最终位流。本目录保留这些回执，没有将Map阶段结果当作最终布线资源。

以上是已采用约束下的内部实现检查，原始回执仍记录ExternalACAccepted=false；报告不将其改写为HDMI外部接口已完成独立AC签核。没有把时序裕量或处理时间倒数当作新校正帧率。

本次精简提交不需要保留历史A/B/C/D大归档。上述冻结来源链接用于历史追溯；离线校验请运行同层[选定包](../submission/README.md)的`verify_selected.py`，它通过source-manifest绑定本目录全部报告。
