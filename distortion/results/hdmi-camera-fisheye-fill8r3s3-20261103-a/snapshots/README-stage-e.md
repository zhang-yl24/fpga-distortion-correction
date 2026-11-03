# 鱼眼矫正 fill8 / R3 Seed 3 结果包

阶段 E，2026-11-03。选定的 S3 位流已下载到易失 SRAM，矫正模式实测 **5.0 个新画面/秒**，比此前 C 版约 4.276 个新画面/秒提高 **16.9%**。用户反馈原文：“画面正常，比之前流畅，但还是有卡顿”。本次未写 Flash；S3 的原图帧率和 KEY1 往返切换尚未测量确认。

当前状态见 [阶段 E 快照](status-snapshot-e.json)，用户原话见 [视觉反馈](user-visual-feedback-e.json)。

## 本次上板结果

| 指标 | S3 矫正实测 | 证据 |
| --- | ---: | --- |
| 采样窗口 | 30 个串口样本，首末相隔 29 秒 | [测率回执](evidence/fps-S3/corrected-receipt.json)、[原始字节](evidence/fps-S3/corrected-wire.bin) |
| 完成的新画面 | 增加 145 帧，即 5.000 FPS | 同上 |
| 独立主机计时 | 5.000101 FPS | [C 与 S3 比较](evidence/fps-S3/independent-C-vs-S3-comparison.json) |
| 显示刷新 / 重复帧 | 30 Hz / 25 Hz | [测率回执](evidence/fps-S3/corrected-receipt.json) |
| 采样窗口新增空白 / 故障 / CRC 拒绝 | 0 / 0 / 0 | 同上 |
| 最末帧处理 | 21,082,909 个核心周期，168.663 ms | 同上 |
| SRAM 下载 | DONE、预期器件和 ID 检查通过；清理错误为空；未写 Flash | [下载回执](evidence/program/receipt.json) |
| 屏幕反馈 | 画面正常、比此前流畅，仍有卡顿 | [用户原话](user-visual-feedback-e.json) |

5 FPS 计数的是完整新结果帧；30 Hz 刷新中有 25 Hz 在重复已有结果。上述处理时间是 RTL 计数值，未测量光学端到端延迟。独立比较重新解析了已保存的 C、S3 串口字节，并核对各自的下载与位流绑定；归档没有重新连接硬件。

## 选定位流与源码

本包包含 [本次选定位流](artifacts/hdmi_camera_fisheye_top.sbit)，供对应板卡的易失 SRAM 流程使用。其大小、六项原生头字段与已通过的 bit 验证回执一致，复制前后 SHA 不变；原文件未改动。它依赖本工程的器件及引脚约束，不是通用板卡固件。

| 项目 | SHA256 / 大小 |
| --- | --- |
| 选定位流 | `ae6be718eaa60fdcd1ba252c08133e7e24d22d247d2a649d21f0d1f7be4a4d16`；3,791,112 字节 |
| 最终物理 ADF | `8510ff44a6c5cba81b675ad3bdf249ba93e1be4f2c372f5ff76b855ba761e2a2` |
| 完整物理证明 | `e2abc4bd5dc9de4f4be940a310974130ae0edec90023f802e8b827e0fd65f9bd` |
| 冻结的 77 项 provider 清单 | `5d6a03f264d445c36bb62ef51be20d015108b6b99d5180ea52b19480e0ba65fe` |

[位流、板上测率与源码索引](selected-bit-board-fps-index-e.json) 保留完整来源路径、SHA、源码绑定及下载/串口回执的对应关系。[bit 计划](evidence/bit/bitstream-plan.json) 与 [下载计划](evidence/program/plan.json) 保留完整输入哈希集合。较大的原始物理证明和报告仅保留精确引用，没有复制到本包。

候选使用 R3 RTL、placement seed 3，物理及发布证明采用 `s3v2-bounded-b`。关键源码归档于 [fill8 R3 缓存](evidence/source/selected-rtl/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v)、[R2 仲裁器](evidence/source/selected-rtl/ddr_read_arbiter_fill8r2.v)、[采样封装](evidence/source/selected-rtl/ddr_remap_sample_scatter16_rowpipe.v)。缓存填充散写由 32 周期改为 8 周期，R3 调整统计计数使能。

## 已完成的实现检查

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 构建与源码比较 | 110 项 RTL/IP/头文件/约束与 R3 对应；命名空间及 placement seed 差异被限定 | [构建](evidence/build/execution-result.json)、[源码比较](evidence/source/full-build-source-api-review.json) |
| 普通核心时序 | slow/fast 十表无失败；slow setup +0.199 ns，slow hold +0.064 ns | [核心十表](evidence/build/raw-core-timing.json) |
| 系统源码仿真 | 两帧 1920×1080，检查 4,147,200 个输出像素；矫正 12,674,663 周期，原图 2,878,738 周期 | [仿真](evidence/simulation/SystemSimulation.json)、[逐帧比较](evidence/simulation/system-native-comparison.json) |
| 发布源码绑定 | v2 发布模块重新绑定 mapper/system/IO/profile 输入；未重复执行同源码系统仿真 | [绑定](evidence/source/selected-v2-release-source-bindings.json) |
| 启动隔离 | 34 个实际 FF、7 个物理 RS 核对；最大需求 2.487 ns，小于 24 ns，裕量约 21.513 ns | [实际字段](evidence/startup/actual-34-native-fields.json)、[完整证明](evidence/startup/full-bounded-b-review.json) |
| 启动与解析器测试 | 28 项启动测试、12 项解析器测试及独立同行复核通过 | [启动](evidence/startup/own-28-tests.json)、[解析器](evidence/startup/parser-12-tests.xml)、[同行复核](evidence/startup/independent-peer-review.json) |
| 完整物理证明 | 主线程复核 778 项输入 SHA；STA、网表、FF 布局、路由、查询和异常覆盖通过，worker 退出 0 | [完成交接](evidence/physical/root-completed-handoff.json)、[证明索引](evidence/physical/final-physical-proof-index.json) |
| bit 生成检查 | 重新 STA、异常/时钟身份、运行时门检、原生执行和 bit 验证通过 | [门检](evidence/bit/pre-bit-audit.json)、[执行](evidence/bit/execution-result.json)、[验证](evidence/bit/verification.json) |

这些检查分别覆盖源码功能、实现时序、数字测率和用户观感。未执行配置逐位回读、光学延迟测量或新的原图/KEY1 往返测试。

## 旧 C 版基线

以下是此前 C 版测量，不能写成 S3 的原图或切换成绩。

| C 版模式 | 处理 FPS | 新画面 FPS | 回执 |
| --- | ---: | ---: | --- |
| 矫正 | 4.310 | 4.276 | [矫正](evidence/baseline-C/corrected-fps-receipt.json) |
| 原图 | 30.000 | 30.000 | [原图](evidence/baseline-C/raw-fps-receipt.json) |
| KEY1 切回矫正 | 4.273 | 4.273 | [切回](evidence/baseline-C/corrected-return-fps-receipt.json) |

同比采用独立主机计时：C 为 4.275951 FPS，S3 为 5.000101 FPS，比例 1.169354。C 末帧处理为 222.479 ms，S3 为 168.663 ms；这些值描述单个样本的处理时间。

## 包内校验与原始追溯

克隆仓库后，用 Python 3.10 或更新版本只读校验随包文件，不依赖原开发机盘符或 `work/` 目录：

```powershell
python distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/verify_archive_portable.py
```

[可移植清单](portable-evidence-manifest-e.json) 使用包内相对路径，包含选定位流及最低限度的下载/测率证据。它只检查随包文件的字节数和 SHA；完整物理复核仍需要未随包提供的大原件。[原始证据清单](approved-evidence-sources-e.json)、回执及部分源码清单保留开发机绝对路径，忠实记录当时来源；这些路径不保证在其他机器存在。源 RTL、构建方法和授权厂商工具应按仓库相应文档使用，包内归档源码仅用于追溯。

原开发机可用以下命令重查显式来源及归档副本；只有结果包的机器不能使用这项来源核验：

```powershell
python distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/copy_evidence_e.py --verify-only
```

归档没有执行 EDA、运行门检、访问硬件、提交或发布。此前不可变记录保留在 [B 说明](snapshots/README-stage-b.md)、[C 说明](snapshots/README-stage-c.md)、[D 说明](snapshots/README-stage-d.md)。

## 后续检查

S3 原图帧率及 KEY1 往返切换尚待确认。矫正仍有卡顿，下一步需要依据真实计数拆分采集、DDR 搬运、矫正与呈现的等待，再选择性能改动；当前结果支持约 16.9% 的新画面帧率提升。
