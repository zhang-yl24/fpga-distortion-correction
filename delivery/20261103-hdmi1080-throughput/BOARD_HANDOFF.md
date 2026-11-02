# 给上板同学的操作交接

目标：在固定纯校正模式下，比较同一输入、同一 K/D、同一时钟和约束的实际输出帧率。优化源码与冻结演示版分目录保存。

## 1. 准备三个独立候选

本地完整包解压后，根目录包含 `native-dependencies/` 和 `delivery/`。先从解压根核验已附的 80 项原生依赖；这一步无需 Git、历史源码目录或 EDA：

```powershell
python -B delivery/20261103-hdmi1080-throughput/tools/recover_native_dependencies.py --verify-only --out native-dependencies
```

预期输出 `passed: true`、`required: 80`、`matched: 80`。随后进入 `delivery/20261103-hdmi1080-throughput`，准备三个独立候选：

```powershell
python -B tools/prepare_candidate.py --dependency-native ../../native-dependencies --output-root C:/fpga-build --run-name corrected-base-01 --variant baseline --mode corrected
python -B tools/prepare_candidate.py --dependency-native ../../native-dependencies --output-root C:/fpga-build --run-name corrected-cache-01 --variant cache --mode corrected
python -B tools/prepare_candidate.py --dependency-native ../../native-dependencies --output-root C:/fpga-build --run-name corrected-both-01 --variant both --mode corrected
```

`../../native-dependencies` 对应完整包的依赖目录；也可改为已核验的其他本地目录。建议使用短输出目录，避免 Windows/PDS 长路径限制；脚本会在写入前拒绝超过 240 字符的源文件目标路径。每个 `C:/fpga-build/<run-name>/preparation.json` 记录 variant、mode、param_id、完整 130 项输入/编译副本哈希和 include 重定位。`native/` 是独立编译副本，`map.tcl` 保留封存工程的设计顺序和器件。

脚本仅准备源文件，不执行 EDA、串口或下载。本地完整包包含已核验的依赖；仅有 GitHub 源码 checkout 时，可按 [依赖恢复说明](DEPENDENCY_RECOVERY.md) 从本地对应源码重建。哈希不匹配时先核对基线版本，避免用不同 DDR IP 或时钟文件拼接。

通过原工程构建流程执行 Map、原 UART 引脚补充、PNR 和双角 STA。重点比较新增 writer 32-word 读 mux、缓存同步读后半字选择的路径；复位/外部 IO 约束仍需按实际板工程签核。记录最终源码、约束、ADF、bit 的哈希和资源。候选达到上板条件后，再由板端操作者下载。

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

固定纯校正 baseline 与 cache 是优先的一组；若 cache 时序及实测改善成立，再测 both。需要回退演示时，使用原封存 bit 及其原恢复步骤。
