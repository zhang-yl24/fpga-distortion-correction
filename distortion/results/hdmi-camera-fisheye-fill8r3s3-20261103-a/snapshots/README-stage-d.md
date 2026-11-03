# 鱼眼矫正 fill8 / R3 Seed 3 结果包

这是 2026-11-03 的阶段 D 结果包，当前状态见 [status-snapshot-d.json](status-snapshot-d.json)。候选硬件采用 R3 RTL、placement seed 3；物理及发布证明使用独立的 `s3v2-bounded-b` 版本。

**完整物理证明已通过，新 bit 也已完成验证，重新 STA 与运行时门检通过。阶段 D 尚未收录 SRAM 下载完成或新版本帧率回执；最后已完成的板上测量仍为 C 版，矫正模式约 4.3 个新画面/秒。**

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
| v2 最终完整物理证明 | 主线程完整核验通过；物理 worker 正常退出 0，重查 778 项输入 SHA；STA、网表、所有 FF 布局、路由、原生查询与精确异常覆盖均按最终证明核验 | [完成交接回执](evidence/physical/root-completed-handoff.json)、[最终证明 SHA 索引](evidence/physical/final-physical-proof-index.json) |
| v2 bit 生成及验证 | 原生执行正常退出 0；重新 STA 十表、时钟摘要和异常路径保持检查通过，运行时门检通过，验证回执为 `Verified: true` | [bit 验证](evidence/bit/verification.json)、[运行时门检](evidence/bit/pre-bit-audit.json)、[执行回执](evidence/bit/execution-result.json)、[bit 证据索引](evidence/bit/bit-verification-index.json) |

最终物理 ADF 的 SHA256 为 `8510ff44a6c5cba81b675ad3bdf249ba93e1be4f2c372f5ff76b855ba761e2a2`。最终物理证明原文件约 65 MB，SHA256 为 `e2abc4bd5dc9de4f4be940a310974130ae0edec90023f802e8b827e0fd65f9bd`，通过索引引用，未重复复制。归档过程只检查原文件 SHA 和报告的通过字段，没有重新推导完整物理证明。该证明中的 `ExternalACAccepted` 与 `RGBPixelsVerified` 仍为 `false`，不能据此写成新版本的板上像素或帧率已验证。

主线程已通知并建立 [后续易失 SRAM 交接](evidence/release/authorized-handoff-before-bit.json)：须先通过实际 bit 的所有检查，再继续 SRAM 流程；Flash 不在授权内。这个交接文件本身不是 bit 或下载完成回执。

本次已验证 bit 为 3,791,112 字节，SHA256 为 `ae6be718eaa60fdcd1ba252c08133e7e24d22d247d2a649d21f0d1f7be4a4d16`，绑定上述最终物理 ADF。原生记录的顺序为重新 STA、运行时门检通过、生成 bit。归档只重新核对验证回执所列 18 份证据的 SHA，以及门检和执行回执之间的引用一致性；没有重新运行门检或读取发布私有缓存。bit 原文件超过本包 2 MiB 的单文件复制上限，当前保留精确引用。该阶段不据此确认当前板上镜像、像素或帧率。

系统仿真执行了 1920×1080 的矫正帧和原图帧，共核对 4,147,200 个输出像素。矫正帧处理为 12,674,663 个系统周期，原图帧为 2,878,738 个周期。这些是源码仿真数据，不能当作本候选的上板 FPS。原始报告及与前版的逐帧、逐周期比较分别归档于 [系统仿真](evidence/simulation/SystemSimulation.json) 和 [等价性比较](evidence/simulation/system-native-comparison.json)。

## 板上 C 版的已测基线

以下仅归档此前完成的 C 版测量，未重新打开串口，也不属于新 Seed 3 候选的成绩。具体时钟基准及独立主机计时信息保留在原回执中。

| C 版模式 | 处理帧率 | 新画面帧率 | 回执 |
| --- | ---: | ---: | --- |
| 矫正 | 4.310 FPS | 4.276 FPS | [矫正测率](evidence/baseline-C/corrected-fps-receipt.json) |
| 原图 | 30.000 FPS | 30.000 FPS | [原图测率](evidence/baseline-C/raw-fps-receipt.json) |
| KEY1 切回矫正 | 4.273 FPS | 4.273 FPS | [切回测率](evidence/baseline-C/corrected-return-fps-receipt.json) |

## 归档与校验

[approved-evidence-sources-d.json](approved-evidence-sources-d.json) 明确列出每份已完成证据的原路径、字节数、SHA256、归档位置及通过条件。当前复制 36 份小回执/清单/测试结果，合计约 1.85 MB；较大的物理执行回执、警告证明、最终完整物理证明及 bit 仅保留精确引用。报告、ADF、网表和源代码仍留在原工作目录；本包是轻量追溯包，完整复核仍依赖这些原文件。

复制工具只处理显式清单，不扫描后续活动阶段，不覆盖不同内容的文件，并核对源文件的 SHA、大小和修改时间前后不变。它不执行 EDA、串口、JTAG、发布或提交操作。

在仓库根目录进行只读核验：

```powershell
D:/anaconda3/python.exe distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/copy_evidence.py --sources approved-evidence-sources-d.json --verify-only
```

需要再次按该清单补齐相同归档时，使用一个新的回执名；已有相同文件只校验、不改写：

```powershell
D:/anaconda3/python.exe distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/copy_evidence.py --sources approved-evidence-sources-d.json --receipt copy-receipt-next.json
```

冻结的 77 项 provider 清单 SHA256 仍为 `5d6a03f264d445c36bb62ef51be20d015108b6b99d5180ea52b19480e0ba65fe`，归档过程未改动该清单或其原始证据。阶段 A、B、C 的清单、状态与 [阶段 B 说明](snapshots/README-stage-b.md)、[阶段 C 说明](snapshots/README-stage-c.md) 完整保留；当前说明以阶段 D 的 `*-d.json` 为准。

## 待最终补齐

1. 新版本易失 SRAM 下载回执。
2. 新版本矫正/原图 FPS、往返切换和屏幕反馈。

主线程提供这些已完成证据后，应新增明确清单及状态快照，再更新本说明；当前的通过项、原始失败记录和冻结输入均保留。本目录尚未对外发布，也未提交到版本库。
