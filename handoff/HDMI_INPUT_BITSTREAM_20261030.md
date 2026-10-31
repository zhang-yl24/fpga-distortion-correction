# HDMI 输入观察器位流与断电交接（2026-10-30）

输入观察器 `hdmi_uart_input_diag` 已从精确 scoped ADF 离线导出位流，新增独立产物复核和仅生成 SRAM 下载计划的工具。用户在本轮明确开发板已断电；本轮没有 JTAG、UART、下载或 Flash 操作，尚无新观察器的实板输入数据。

[结构化结果](../distortion/results/hdmi-input-bitstream-20261030.json)和[68 项原始证据及双哈希清单](../distortion/results/hdmi-input-bitstream-20261030/manifest.json)记录本次交付。压缩的原生报告/ADF/网表解压后须匹配各项 `SourceSHA256`；旧 CDC 证据清单保持原字节。包含位流与原始工作输入的独立 ZIP 已在本机生成、校验，尚未上传或发布，路径和哈希见结果文件的 `LocalArchive`。

## 位流与来源

| 对象 | 绑定 |
|---|---|
| 本机位流 | `distortion/build/hdmi-uart-diagnostic/input-bit-1030-a/generate_bitstream/hdmi_uart_input_diag.sbit` |
| 位流长度 | 3,791,112 字节 |
| 位流 SHA256 | `4aa42d6fc582385ea584c68a86d796bc26fcc8568c337abe053a2e6a41ad63dc` |
| 实际输入 ADF SHA256 | `d7858e4b705469e6619ba3c99df2c78bf47e2e4f515aeb3b328ea67c70c676a8` |
| 位流头 | `hdmi_uart_input_diag` / `Logos2-PG2L100H--6-FBG676` / `2023.2-SP3<154097>` |
| 生成时间 | 北京时间 2026-10-30 11:01:12 |

本次导出未重新综合或布局布线。原生日志实际阶段为 Report Timing → 运行时审计通过 → Generate Bitstream，原生退出 0；STA 与位流生成命令均显式使用同一 `audited-final.adf`。19 项工程输入和 20 项工作输入未漂移，原始准备器字节保持不变。

双角十类汇总、时钟、每角 167 条 8 ns MaxDelay 和限定例外均与封存基线一致。每角 setup false-path 为 0、hold 为 167、recovery/removal 各为 4。内部最差裕量如下：

| 角 | setup | hold | recovery | removal | MPW |
|---|---:|---:|---:|---:|---:|
| slow | +1.079 ns | +0.157 ns | +0.659 ns | +0.184 ns | +6.457 ns |
| fast | +1.869 ns | +0.104 ns | +1.889 ns | +0.026 ns | +6.457 ns |

这些结论仅覆盖报告里的内部检查。外部 IO 未约束告警、6 条历史 `PAP_ASYNC_REG` 警告与物理 CDC/MTBF 边界保留，`HardwareReleaseAllowed=false`。

本轮还从同一精确 ADF 在 `input-bit-final-export-1030-a` 直接导出功能网表，原生退出 0，原与副本 ADF 均未变化。5004 个解析单元的类型、参数、端口、连接、驱动关系及导出位置均与基线相同；46 脚和方向、161 个同步 FF、81 对同 CLM 的直接级间连接逐项通过。新网表 SHA256 为 `df6fd73bdc0b293adb4719f55623f4060568202c8776ded736f7ad04086290dd`。输出引脚通过导出 primitive 站点与未变的封装引脚表映射，标量输入/双向脚通过导出属性核查。

该次只请求 5 条详细时序路径，用于网表导出，不代替位流生成前的完整例外审计。首次导出后的属性正则分析过慢，已停止自有 Python 进程并保留原脚本、成功 PDS 回执和中断记录；限定属性范围的新解析器复核通过。

## 原始失败回执为何保留

上一轮 `export-result.json` 为 `Passed=false`，原因为收尾断言把 PDS 解析工程时的 `Executing compile/synthesize/dev_map/pnr` 声明误作实际阶段。其 `ReturnCode=0`，原生日志已完成位流生成。原始 JSON 和日志保持原字节，独立复核通过不会覆盖它。

新增 [verify_hdmi_input_bitstream.py](../distortion/tools/verify_hdmi_input_bitstream.py) 使用 `Process ... started/done` 识别实际阶段，检查准确的审计标记和生成命令顺序，重算原始回执日志哈希、生成前审计、原生时序及例外，固定本次位流字节/头/ADF。仅精确识别这一次阶段分类错误，其他失败拒绝。该工具不启动 EDA 或访问开发板。

## 离线复核与下载计划入口

从仓库根目录执行，输出文件或工作目录须使用新后缀：

```powershell
.\.venv\Scripts\python.exe distortion/tools/verify_hdmi_input_bitstream.py --workdir distortion/build/hdmi-uart-diagnostic/input-bit-1030-a --output distortion/results/hdmi-input-bit-verification-new.json
.\.venv\Scripts\python.exe distortion/tools/prepare_hdmi_input_program.py --bit-work distortion/build/hdmi-uart-diagnostic/input-bit-1030-a --workdir distortion/build/offline-20261024/hdmi-input-program-new --frequency 1MHz
```

准备器先重新运行独立复核，再绑定所有输入、位流及工具，生成分离的 `scan.tcl`、`program.tcl` 和 `plan.json`。它没有执行模式，计划不代表设备识别或 DONE。实际计划见证据包中的 `download-plan/`；用户重新供电后仍须重新核验文件、只读识别 PG2L100H / `0x00602899`，再按受控 SRAM 流程执行。通用 `program_native_raw.py` 的公开入口仅接受固定 CAM2 目标，不能直接拿它下载此观察器。

## 重新供电后的输入判定

下一次实板操作先核对电脑→HDMI IN、HDMI OUT→显示器及 UART，重新下载观察器。随后用 COM7 / 115200 / 8N1 有限只接收窗口保存原始字节：

```powershell
.\.venv\Scripts\python.exe distortion/tools/hdmi_status.py --port COM7 --seconds 5 --output distortion/results/hdmi-input-live-new.json
.\.venv\Scripts\python.exe distortion/tools/assess_hdmi_input.py --wire distortion/results/hdmi-input-live-new.raw.bin --receipt distortion/results/hdmi-input-live-new.json --output distortion/results/hdmi-input-assessment-new.json
```

以上两条留待用户重新供电后执行，本轮未运行。评估器要求至少 1 秒连续合格窗口：配置新鲜且完成、尺寸 1920×1080、1 ms 窗口像素时钟边沿数 73,500–75,000、无配置/输入错误、好帧计数持续前进且与固定 2200×1125 光栅速率相容。它拒绝中间包损坏、丢序或复位及窗口内失格，不会静默挑选后续好包覆盖失败。

帧率估计使用额定 27 MHz 参考时钟、端点一帧量化和每端最多 2 ms 快照年龄模型，并非示波器测量。UART 协议没有可认证的位流身份；CRC/回执一致不证明物理来源。该观察器不采输入像素，也不含 DDR 或畸变主链，因此输入几何通过后仍须继续集成并单独验收整链。

原彩条来自旧 `hdmi_uart_delayed_diag`。用户已断电，不能把历史 DONE=1 当作当前 SRAM 配置仍有效。温度状态保持未核实，测温支线按最新用户指示暂停。

## 本轮验证

相关六组 CPU 测试共 **179 项通过**，包含损坏包、旧诊断、不连续窗口、时序/例外篡改、错误位流、原始失败回执识别和计划不访问硬件等检查，已纳入 CI。四个交付基线及依赖闭包审计通过。旧彩条诊断的 10 包原始串口离线评估得到传输一致、`no_qualified_input_window`，验证它不能冒充观察器输入通过；这不是一次新硬件接收。原始输出与 JUnit 日志均已封存。
