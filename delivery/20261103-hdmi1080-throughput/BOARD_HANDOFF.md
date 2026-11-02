# 给上板同学的操作交接

目标：在固定纯校正模式下，比较同一输入、同一 K/D、同一时钟和约束的实际输出帧率。优化源码与冻结演示版分目录保存。

## 1. 已生成的三个诊断候选与重建方式

baseline、cache、both 已在 `D:/fpga-build/<variant>-final` 完成 Map、布局布线、双角 STA 和诊断 `.sbit` 生成。144 个实际引脚、全部声明电气属性和 11 个时钟均通过审计；尚未下载或板测。当前 slow setup 为 baseline 62 个端点 / -0.659ns、cache 155 / -0.762ns、both 16 / -0.619ns；三版 DDR recovery/removal 仍有违规，外部 IO 时序待签核。完整证据见 [summary.json](evidence/board/summary.json)。

优先比较 **baseline → both**，cache 用作单项优化对照。完整包根目录提供：

| 配置 | param_id | 位流路径 |
|---|---|---|
| baseline | `b0481b1d` | `bitstreams/baseline/baseline_corrected_b0481b1d_DIAGNOSTIC_NOT_TIMING_SIGNOFF.sbit` |
| both | `f36cb459` | `bitstreams/both/both_corrected_f36cb459_DIAGNOSTIC_NOT_TIMING_SIGNOFF.sbit` |
| cache | `1a247c5b` | `bitstreams/cache/cache_corrected_1a247c5b_DIAGNOSTIC_NOT_TIMING_SIGNOFF.sbit` |

各位流目录附 `STATUS.json`，构建回执位于包根 `board-builds/<variant>/`。位流已通过生成与身份核验；回执中的 `physical_timing_accepted`、`hardware_release_allowed` 仍为 `false`。板端操作者应按诊断状态核对当前硬件和失败项目，并记录实际测试结果。

本地完整包解压后，根目录包含 `native-dependencies/` 和 `delivery/`。先从解压根核验已附的 80 项原生依赖；这一步无需 Git、历史源码目录或 EDA：

```powershell
python -B delivery/20261103-hdmi1080-throughput/tools/recover_native_dependencies.py --verify-only --out native-dependencies
```

预期输出 `passed: true`、`required: 80`、`matched: 80`。如需重建，进入 `delivery/20261103-hdmi1080-throughput`，在空间充足的短路径创建新工程；以下显式选择 both：

```powershell
$flow = 'tools/build_board_candidate.py'
$pds = 'E:/PDS_2025.2-ads-win64/pango/PDS_2025.2-ads/bin/pds_shell.exe'
python -B $flow prepare --dependency-native ../../native-dependencies --output-root D:/fpga-build2 --run-name corrected-both-01 --variant both --mode corrected
$work = 'D:/fpga-build2/corrected-both-01'
python -B $flow run --work $work --stage map --pds-shell $pds
python -B $flow run --work $work --stage route --pds-shell $pds
python -B $flow run --work $work --stage sta --pds-shell $pds
python -B $flow run --work $work --stage bitstream --pds-shell $pds --diagnostic-bit
```

`../../native-dependencies` 对应完整包的依赖目录；也可改为已核验的其他本地目录。PDS 路径替换为本机实际安装位置。构建入口默认 variant 为 `cache`，例子明确覆盖为 `both`；准备 baseline 或 cache 时同时改用对应 `--variant` 和新的 run 名。建议解压到 `D:/fpga` 等短路径；脚本拒绝超过 240 字符的源文件目标路径，EDA 启动前检查可用空间。

每个新工程的 `preparation.json` 记录 variant、mode、param_id、完整 130 项输入/编译副本哈希和 include 重定位。`native/` 是独立编译副本；生成后保留其目录位置。prepare 仅准备源码，后续 run 命令执行对应 EDA 阶段，整个脚本不调用串口或下载。本地完整包包含已核验的依赖；仅有 GitHub checkout 时，可按 [依赖恢复说明](DEPENDENCY_RECOVERY.md) 从本地对应源码重建。哈希不匹配时先核对基线版本。

构建工具为每阶段显式导入原 FDC、UART 引脚补充和 Map PCF，复核最终引脚、电气属性、时钟及同一 ADF 身份。`--diagnostic-bit` 保留全部时序失败记录和诊断标记；正式签核仍需收敛 setup、DDR 复位与外部 IO 时序。完整命令说明见 [BOARD_BUILD_NOTES.md](docs/BOARD_BUILD_NOTES.md)。

这三个配置保留封存输入准入与输出约 30Hz 时序。先用电脑的同一 1080p29.97 输入复测；摄像头 60Hz 直通版的位流、时序或性能不能代入本路径。

## 2. 固定模式采集与统计

`--mode corrected` 从复位后始终选择校正，Gamma OFF。`raw` 固定原图处理路径，`demo` 保留约三秒切换。性能对比使用 corrected。

每个候选先稳定出图，丢弃预热阶段，再使用原来的 b4 LOAD/ARM 与原始 UART 记录流程采集至少 60 秒；条件允许时补充更长连续窗口。采集器需要记录实际单调时钟起止时间、session nonce、原始接收字节。新候选的 param_id 从对应 preparation.json 读取，并用于原接收器的身份白名单。参数标识是构建身份，session nonce 仍由原会话流程提供。

本工具只分析已有字节文件，不打开串口、不发送控制命令：

```powershell
python -B tools/analyze_scan.py C:/capture/uart.bin --seconds 60.066112 --param-id 0123abcd --session-id 12345678 --output C:/capture/scan-analysis.json
```

示例中的路径、时长和十六进制 ID 均需换成本次实际值。输入为二进制原始 UART 字节，避免传入十六进制文本。工具核验现有 PGSIG001 协议的包 CRC、版本、长度、尾标、session/param_id、固定 mode=1、2073600 像素及采样 mask；区分完整扫描次数、不同帧 ID 数和重复扫描。错包、混合模式、序列/扫描 epoch 缺口、observer 错误等会使 `accepted_unique_display_fps` 返回 null 并退出失败，同时保留观察计数。

统计值使用“窗口内完整记录数 ÷ 实际采集秒数”。相同 frame ID 的重复显示不增加唯一帧数，相同 ID 的 CRC 变化单独报错。窗口最后一个不完整包单独列出。该测量反映最终数字扫描的新帧更新，内部处理耗时、物理 HDMI 接收显示延迟仍需单独测量。

## 3. 若帧率仍受限，继续区分等待原因

当前 `hdmi1080_video_system_geometry_ab` 已有以下 core 域输出，但封存 top 没有把它们全部导出到 UART：

| 信号 | 用途 |
|---|---|
| captured_frames / processed_frames / presented_frames | 分别观察被接受的采集、完成处理、成功扫描的新帧数 |
| last_process_cycles | 最近一帧 source 接受至 engine 完成的核心周期 |
| processing / pending / display_active | 判断处理忙、结果待发布、显示占用 |
| cache_misses / cache_hits / queries | 缓存工作量；这些计数的帧/累计语义以 RTL 为准 |
| underflows / mismatches | 显示读出异常 |

需要内部计时的版本，可在同一 core 域增加被动计数快照，再通过保持握手跨域导出；保持帧 ID 与 cycle 数据对应。此次交付沿用扫描遥测协议，未把 last_process_cycles 填入现有扫描包。

若处理周期下降而唯一显示 FPS 没变，优先检查 source bank 等待、pending 等待与输入丢帧；若处理耗时仍占主导，再查看当前真实标定下的 cache miss 和 DDR 仲裁。当前两源/两结果 bank 的所有权规则需完整保留。

## 4. 回传最小验收材料

每个候选提供：preparation.json、最终综合/时序摘要、bit SHA256、输入模式、真实标定参数哈希、session ID、采集起止时间、原始 UART、scan-analysis.json，以及同一测试场景短视频。对比表至少列出唯一输出 FPS、重复比例、内部周期（如有）、运行时长、错误计数、LUT/FF/DRM/APM 和最差 setup/hold。

固定纯校正 baseline 与 both 是优先的一组，cache 用于定位单项优化收益。三版完整工程 Map 资源分别为 FF/LUT：baseline 21,898/17,066、cache 21,964/17,162.5、both 26,418/18,292.5；DRM 均为 19.5，APM 均为 69。需要回退演示时，使用原封存 bit 及其原恢复步骤。
