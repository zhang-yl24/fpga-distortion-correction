# tile8／双条带鱼眼矫正候选：阶段 A

2026-11-03。本包保存已经完成的 tile8 源码、单元测试、完整 1080p 仿真、普通核心时序、原生导出和启动复核。当前状态见 [阶段 A 快照](status-snapshot-a.json)。

**tile8 尚无最终完整物理证明、选定位流、下载回执或板上 FPS。当前最后完成的板上证据仍是 S3 矫正 5 FPS；用户“画面正常，比之前流畅，但还是有卡顿”的反馈也只属于 S3。**

## 已完成的功能与性能仿真

矫正帧按 8×8 tile 顺序提交坐标，双条带写入器将结果重排为光栅 DDR 突发；原图保持光栅顺序。模式在帧开始锁定，源帧所有权、像素与标签的弹性缓冲以及完整结果发布条件保留。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 独立引擎测试 | 4 个完整帧；tile／原图顺序、帧中模式变更、背压、逐像素与 CRC、复位中断恢复及重叠地址拒绝通过 | [引擎单元回执](evidence/simulation/engine-unit.json) |
| 双条带写入器 | 5 种尺寸、18 个完整 raw／tile 帧、9 类故障；逐像素与 Python CRC 比较通过 | [写入器回执](evidence/simulation/writer-unit.json) |
| 真实系统小规模仿真 | 1024 个输出像素；三次 KEY1 事件、模式锁存、复位与最终排空检查通过 | [小规模回执](evidence/simulation/system-small.json) |
| 完整 1080p 双帧仿真 | 4,147,200 个输出像素全部与 CPU 参考一致；输入／输出 CRC、帧所有权、KEY1 与排空检查通过，无下溢或丢帧 | [完整回执](evidence/simulation/system-native1080.json)、[逐帧 CSV](evidence/simulation/full1080/frames.csv) |
| 独立语义比较 | 与已完成 R3 参考的夹具、输入／输出 CRC、计数、模式、每帧所有权和事件顺序语义一致 | [独立比较](evidence/simulation/independent-semantic-comparison.json) |
| 实际发布模块源码绑定 | 选定 tile8v2 bit 模块重新核对完整系统仿真、生产源码／头文件及实际编译角色 | [源码绑定](evidence/source/selected-v2-system-source-binding.json) |

| 仿真指标 | R3／S3 参考 | tile8 |
| --- | ---: | ---: |
| 矫正处理周期 | 12,674,663 | 3,967,406 |
| 矫正缓存填充次数 | 275,060 | 49,465 |
| 原图处理周期 | 2,878,738 | 2,878,504 |
| 原图缓存填充次数 | 16,200 | 16,200 |

矫正模拟周期约减少 68.7%，缓存填充约减少 82.0%。在模型的 125 MHz 时钟下，矫正处理为 31.739 ms；它不代表板上 FPS 或光学延迟。观测计数见 [周期分解](evidence/simulation/full1080/performance.csv)，包含坐标阻塞、写入背压、缓存 AR／R 等待、填充和帧末排空；这些等待计数可能重叠，不能直接相加。源码字节、实际编译快照和性能指标的对应见 [绑定索引](evidence/simulation/native-performance-source-binding.json)。

## 已完成的实现证据

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 原生构建 | 正常退出 0，输入无漂移；当前位流尚未生成 | [计划](evidence/build/plan.json)、[执行](evidence/build/execution-result.json) |
| 普通核心时序 | slow／fast 十表均无失败；slow setup +0.122 ns，slow hold +0.061 ns | [十表摘要](evidence/build/raw-core-ten-tables.json) |
| 原生网表／路由导出 | 本次各自回执通过，源 ADF 和独立副本均未变化 | [网表回执](evidence/native/export-receipt.json)、[路由回执](evidence/native/route-receipt.json) |
| 当前启动测试 | 28 项全部通过，使用本次实际网表与路由 Verilog | [28 项回执](evidence/startup/own-28-tests.json) |
| 独立实际单元解析 | 34 个 FF、动态导出的 9 个 RS 引脚；逐单元参数、复位网和布局一致 | [字段复核](evidence/startup/current-native-field-review.json) |
| 完整启动路由复核 | 最大需求 4.27 ns，小于 24 ns 窗口，裕量 19.73 ns，缺失和违例为空 | [限定启动证明](evidence/startup/full-bounded-review.json) |
| 源警告分类 | 当前源警告分类通过，原诊断保留；没有将新像素数据清理归为元数据 | [摘要](evidence/warnings/source-warning-summary.json)、[与 S3 的差异](evidence/warnings/current-vs-S3-warning-origin-review.json) |
| 冻结发布输入 | 431 项代码／证据输入已冻结，原 S3 清单保持不变 | [冻结清单](evidence/source/frozen-431-provider-source-manifest.json) |

源警告分类不是清除编译器警告，也不替代最终原生警告、物理时序、DDR、复位和 CDC 的独立接受。当前普通核心十表和限定启动证明通过，也不等于完整最终物理证明已完成。

关键生产文件的原字节归档于 [tile8 引擎](evidence/source/production/rtl/experimental/hdmi_camera_fisheye_engine_tile8.v)、[双条带写入器](evidence/source/production/rtl/experimental/ddr_adaptive_result_writer_dualstripe.v)、[bank 封装](evidence/source/production/rtl/experimental/hdmi_camera_fisheye_bank_tile8.v)。其余实际执行的生产 RTL 和头文件也保存在 `evidence/source/production/`；这是追溯快照，不是包含全部厂商 IP、夹具和工具的独立重建项目。

## 当前板上 S3 基线

以下只记录此前已完成的 S3 证据，与 tile8 仿真分开：

- S3 易失 SRAM 下载成功，未写 Flash：[下载回执](evidence/baseline-S3/program-receipt.json)。
- S3 矫正新画面 5.0 FPS、刷新 30 Hz：[测率回执](evidence/baseline-S3/corrected-fps-receipt.json)。
- S3 用户原话：“画面正常，比之前流畅，但还是有卡顿”：[原始反馈](evidence/baseline-S3/user-visual-feedback.json)。

这些事实不能作为 tile8 的视觉确认或板上成绩。S3 的结果包仍完整保存在 [原阶段 E 结果](../hdmi-camera-fisheye-fill8r3s3-20261103-a/README.md)。

## 离线校验与限制

Python 3.10 或更新版本可校验随包文件，不依赖原机器盘符或 `work/`：

```powershell
python distortion/results/hdmi-camera-fisheye-tile8-20261103-a/verify_archive_portable.py
```

[便携清单](portable-evidence-manifest-a.json) 使用包内相对路径，只验证随包字节和 SHA。六份大型原件——警告完整证明／清单、原生网表、路由 Verilog、ADF、完整时序报告——只保留精确引用，没有复制。大文件和仿真夹具未全部提供，因此本包不能独立重新推导完整仿真或物理证明。

[原始来源清单](approved-evidence-sources-a.json) 保留原路径、大小、SHA 和通过字段；原始回执中的绝对路径忠实保留，不能假定在其他机器存在。只有原开发机具备全部来源时，才可运行：

```powershell
python distortion/results/hdmi-camera-fisheye-tile8-20261103-a/copy_evidence.py --verify-only
```

归档未执行 EDA、门检、硬件操作、提交或发布，也没有读取正在运行的物理阶段或修改冻结的 431 项输入。后续应新增阶段清单和状态，补入实际完成的最终物理证明、bit 验证／选定文件、SRAM 下载、原始串口字节、板上测率与用户反馈；当前阶段保持不可变。
