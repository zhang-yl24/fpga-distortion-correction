# 鱼眼矫正 fill8 / R3 Seed 3 结果包

这是 2026-11-03 的阶段结果包，当前状态见 [status-snapshot-b.json](status-snapshot-b.json)。候选硬件采用 R3 RTL、placement seed 3；物理及发布证明使用独立的 `s3v2-bounded-b` 版本。

**新版本尚未生成 bit、下载 SRAM 或测量帧率。板上仍是 C 版，矫正模式约 4.3 个新画面/秒。**

## 当前已完成的检查

| 项目 | 本快照状态 | 证据 |
| --- | --- | --- |
| Seed 3 原生构建 | 通过；源码、IP、头文件及约束与 R3 一致，仅命名空间路径和 placement seed 改变 | [构建回执](evidence/build/execution-result.json)、[源码核对](evidence/source/full-build-source-api-review.json) |
| 原始普通核心时序 | slow/fast 共十张表均无失败；slow setup 为 +0.199 ns，slow hold 为 +0.064 ns | [核心十表](evidence/build/raw-core-timing.json) |
| 原始网表及路由导出 | 两份本次回执通过，源 ADF 及独立副本未变 | [网表导出](evidence/native/export-result.json)、[路由导出](evidence/native/route-result.json) |
| 源码仿真及发布输入绑定 | 通过；三种仿真由选定 v2 发布模块重新绑定，未重跑约 22 分钟的同源码系统仿真 | [v2 输入绑定](evidence/source/selected-v2-release-source-bindings.json) |
| 启动隔离证明 | 34 个实际 FF、7 个物理 RS 引脚完整核对；最大需求 2.487 ns，小于 24 ns 启动窗口，裕量约 21.513 ns | [实际单元字段](evidence/startup/actual-34-native-fields.json)、[完整限定证明](evidence/startup/full-bounded-b-review.json) |
| 启动及解析器测试 | 28 项启动测试、12 项解析器测试通过；另有独立同行复核 | [28 项结果](evidence/startup/own-28-tests.json)、[12 项结果](evidence/startup/parser-12-tests.xml)、[独立复核](evidence/startup/independent-peer-review.json) |
| v2 物理约束应用 | 执行及根线程绑定通过，耗时 341.9 秒；回执报告路由、布局不变 | 完整回执约 108 MB，仅在 [SHA 索引](approved-evidence-sources-b.json) 中引用原文件 |
| v2 应用后的独立 STA | 本次 scoped export 回执通过，实际 slow/fast 十张表全部通过 | [导出回执](evidence/physical/export-scoped-v2-result.json)、[重新读取的十表摘要](evidence/physical/scoped-ten-sta-table-summary.json) |

当前物理 ADF 的 SHA256 为 `8510ff44a6c5cba81b675ad3bdf249ba93e1be4f2c372f5ff76b855ba761e2a2`。上表的局部通过不等于最终完整物理证明；精确异常覆盖、全部原生查询、最终路由核对及最终证明仍待主线程完成。

系统仿真执行了 1920×1080 的矫正帧和原图帧，共核对 4,147,200 个输出像素。矫正帧处理为 12,674,663 个系统周期，原图帧为 2,878,738 个周期。这些是源码仿真数据，不能当作本候选的上板 FPS。原始报告及与前版的逐帧、逐周期比较分别归档于 [系统仿真](evidence/simulation/SystemSimulation.json) 和 [等价性比较](evidence/simulation/system-native-comparison.json)。

## 板上 C 版的已测基线

以下仅归档此前完成的 C 版测量，未重新打开串口，也不属于新 Seed 3 候选的成绩。具体时钟基准及独立主机计时信息保留在原回执中。

| C 版模式 | 处理帧率 | 新画面帧率 | 回执 |
| --- | ---: | ---: | --- |
| 矫正 | 4.310 FPS | 4.276 FPS | [矫正测率](evidence/baseline-C/corrected-fps-receipt.json) |
| 原图 | 30.000 FPS | 30.000 FPS | [原图测率](evidence/baseline-C/raw-fps-receipt.json) |
| KEY1 切回矫正 | 4.273 FPS | 4.273 FPS | [切回测率](evidence/baseline-C/corrected-return-fps-receipt.json) |

## 归档与校验

[approved-evidence-sources-b.json](approved-evidence-sources-b.json) 明确列出每份已完成证据的原路径、字节数、SHA256、归档位置及通过条件。当前复制 28 份小回执/清单/测试结果，合计约 1.62 MB；较大的物理执行回执和警告证明仅保留精确引用。报告、ADF、网表和源代码仍留在原工作目录；本包是轻量追溯包，完整复核仍依赖这些原文件。

复制工具只处理显式清单，不扫描后续活动阶段，不覆盖不同内容的文件，并核对源文件的 SHA、大小和修改时间前后不变。它不执行 EDA、串口、JTAG、发布或提交操作。

在仓库根目录进行只读核验：

```powershell
D:/anaconda3/python.exe distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/copy_evidence.py --sources approved-evidence-sources-b.json --verify-only
```

需要再次按该清单补齐相同归档时，使用一个新的回执名；已有相同文件只校验、不改写：

```powershell
D:/anaconda3/python.exe distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/copy_evidence.py --sources approved-evidence-sources-b.json --receipt copy-receipt-next.json
```

冻结的 77 项 provider 清单 SHA256 仍为 `5d6a03f264d445c36bb62ef51be20d015108b6b99d5180ea52b19480e0ba65fe`，归档过程未改动该清单或其原始证据。较早的 `*-a.json` 快照保留为过程记录，当前说明以 `*-b.json` 为准。

## 待最终补齐

1. v2 最终物理证明及全部原生检查回执。
2. 新 bit 的生成、重新 STA 与校验回执。
3. 新版本易失 SRAM 下载回执。
4. 新版本矫正/原图 FPS、往返切换和屏幕反馈。

主线程提供这些已完成证据后，应新增明确清单及状态快照，再更新本说明；当前的通过项、原始失败记录和冻结输入均保留。本目录尚未对外发布，也未提交到版本库。
