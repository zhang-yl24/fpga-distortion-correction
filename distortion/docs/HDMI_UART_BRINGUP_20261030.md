# HDMI UART 板级诊断交接（2026-10-30）

当前 PG2L100H 板内运行的是 **100 ms 延迟版 hdmi_uart_delayed_diag**：仅下载易失 SRAM，重新扫描确认 DONE=1，未写 Flash。COM7 首次收到 10 个 CRC 正确的状态包，追加 20 秒收到 40 包；cfg_error 均为 0，成功 I²C 事务持续增加。此前无额外等待的 control 版出现 cfg_error=1、成功事务数=0，基线保留。一次对照表明延迟版恢复了 ACK，尚未通过反复冷启动确认根因；20 秒观测属于短窗验证，不是长稳或 HDMI 视频验收。

本轮没有连接 HDMI 信号源/显示器；当前候选不含 DDR、摄像头、畸变矫正或输入观察器。FPGA 侧保留自生 1920×1080p30 彩条时序，但 TX 初始化等待 RX 完成；目前 RX/ALL done 均 false，不能据此认定 HDMI 已输出图像。历史队友的实板结果不能代替本次观测。

## 候选及实际结果

以下 build/ 路径均相对 distortion/，包含本机原始报告。可随仓库交接的回执和原始串口字节在 [results/hdmi-uart-20261030/files.json](../results/hdmi-uart-20261030/files.json)，该索引记录原路径及 SHA256。位流、ADF 和完整原生报告仍在本机 build/；完整证据压缩包由主线程另行归档。

| 候选 | 实际结果 | 使用边界 |
|---|---|---|
| board/hdmi_uart_diag.v；build/hdmi-uart-diagnostic/pds-1030-a/ | 构建退出 0，但 input_pixel ↔ board27 的 STA 失败；46 脚匹配 | 完整观察器候选保留失败报告，不能用于上板放行 |
| board/hdmi_uart_control_diag.v；build/hdmi-uart-diagnostic/control-pds-1030-a/ | 10 源、42 独立脚，316.513 秒；双角十类 STA 均 0 失败，输入无漂移 | 无额外等待的诊断基线；实板首笔器件地址 NACK |
| build/hdmi-uart-diagnostic/control-bit-1030-a/；hdmi-uart-control-program-1030-a/ | 自身 ADF 导出 3,791,112 字节位流，SRAM DONE=1、未写 Flash | 历史基线；已被延迟版替换，不代表视频正常 |
| board/hdmi_uart_delayed_diag.v；build/hdmi-uart-diagnostic/delayed-pds-1030-a/ | 10 源、42 独立脚，195.25 秒；双角十类 STA 均 0 失败，无时序例外，输入无漂移 | 外设复位释放后再等待 100 ms 才允许配置；仍为独立诊断 |
| build/hdmi-uart-diagnostic/delayed-bit-1030-a/；hdmi-uart-delayed-program-1030-a/ | 自身 ADF 导出 3,791,112 字节位流；ADF/输入无漂移；SRAM DONE=1、未写 Flash | 当前在板；短窗 I²C/串口通信通过，外部 IO AC、上拉和真实视频仍未验收 |

下载目录位于 build/offline-20261024/；已归档的 [control 下载回执](../results/hdmi-uart-20261030/hdmi-uart-control-program-1030-a/receipt.json)与 [delayed 下载回执](../results/hdmi-uart-20261030/hdmi-uart-delayed-program-1030-a/receipt.json)均明确 volatile_sram_only、done_confirmed=true、flash_written=false。

control 版仅删除输入观察器、pixclk_in/vs_in/hs_in/de_in 四脚及 input_pixel 时钟，原配置、遥测和 TX 图案段保持不变。观察字段为不可用的零值；解码结果 pclk_observation_available=false、pclk_edges_observed=null，不能解释为“实测无像素时钟”。delayed 版再增加外设复位后的配置等待，不增加自动重试。

最差裕量（Slow / Fast，ns）：control 的 setup +1.291/+2.028、hold +0.157/+0.115、recovery +0.405/+1.644、removal +0.290/+0.101、脉宽 +6.534/+6.534；delayed 分别为 +1.226/+2.094、+0.159/+0.109、+0.685/+1.873、+0.225/+0.109、+6.534/+6.534。见 [delayed 原生审计](../results/hdmi-uart-20261030/delayed-pds-1030-a/native-audit.json)。此处仅指原生已报告检查；HardwareReleaseAllowed 仍为 false。

完整观察器候选各类失败数（Slow / Fast）：setup 190/190、hold 189/189、recovery 471/471、removal 3/6、脉宽 0/0。原报告没有时序例外，不能添加整域 false-path 来掩盖这些失败。后续须处理 Gray 总线、握手快照及跨域复位释放；本次 PDS 明确忽略 async_reg 属性，不能把该属性当物理同步器保护证据。

## COM7 真实观测与协议

三次观测均为 CP210x COM7、115200/8N1，只接收且发送字节数为 0，DTR/RTS 均为 false。时间为北京时间 2026-10-30。

| 候选及时间 | 原始数据与完整性 | 配置状态 |
|---|---|---|
| control，00:30:13–00:30:19 | 640 字节、10 包，序号 140–149，拒绝包 0 | cfg_error=1，cfg_failed=true，成功事务数 0 |
| delayed，00:50:55–00:51:00 | 640 字节、10 包，序号 94–103，拒绝/噪声/残尾均 0 | cfg_error=0，flags=0x000f，成功事务数 311623→341865 |
| delayed，00:52:22–00:52:42 | 2560 字节、40 包，序号 268–307，拒绝/噪声/残尾均 0 | cfg_error=0，flags=0x000f，成功事务数 896301→1027350；首末包跨度 19.5 秒，净增 131049 |

证据：[control 回执](../results/hdmi-uart-20261030/control-bit-1030-a/live-status-1030-a.json)及[原始字节](../results/hdmi-uart-20261030/control-bit-1030-a/live-status-1030-a.raw.bin)；[delayed 首次回执](../results/hdmi-uart-20261030/delayed-bit-1030-a/live-status-1030-a.json)及[原始字节](../results/hdmi-uart-20261030/delayed-bit-1030-a/live-status-1030-a.raw.bin)；[追加 20 秒回执](../results/hdmi-uart-20261030/delayed-bit-1030-a/live-status-1030-b.json)及[原始字节](../results/hdmi-uart-20261030/delayed-bit-1030-a/live-status-1030-b.raw.bin)。

flags=0x000f 表示 cfg_snapshot_valid/fresh、cfg_pll_locked/video_pll_locked 均为 true；cfg_failed=false，RX/ALL done 仍为 false。最后成功事务为 RX 读事务，首次采样地址在 0x209C–0x209E，追加采样覆盖 0x209C–0x209F；与 RX 控制器 STA_RD 轮询输入状态、尚未满足继续初始化条件一致。计数持续增长说明配置通信有进展，不能解释为 RX/TX 初始化或画面已经通过。

control 的 error 1 对应 checked I²C 驱动的首个器件地址字节 NACK，首目标为 RX 写地址字节 0x56（7 位地址 0x2B）。其 completed_transactions=0，last_address=0 不能当失败寄存器地址。延迟版一次恢复 ACK 支持复位后等待不足的排查方向，但还没有排除冷启动差异、电气/上拉等因素，不能仅凭未接 HDMI 归因。

PGHDMI01 每包 64 字节、小端；头为 PGHDMI01，尾为 HM01，build tag 为 0x48444901，CRC32 覆盖字节 0–55。包包含序号、参考时钟计数、状态标志、配置错误、观察字段、配置快照年龄、成功事务数及最后一笔地址/值/meta；meta bit0=read，bit1=TX。完整定义见 [hdmi_diag_uart.v](../rtl/experimental/hdmi_diag_uart.v) 与 [hdmi_status.py](../tools/hdmi_status.py)。

接收回执 passed=true 的范围是 packet_integrity_only。两个 PLL lock 是 FPGA PLL 状态，不是 HDMI PHY lock；init_done 也不证明颜色格式或正确画面。RX 序列可能等待真实输入状态才置 done，TX 随后启动。

离线证据：[UART 8 场景](../results/hdmi-uart-20261030/uart-1029-a/simulation-result.json)及[真实线级 I²C 7 场景](../results/hdmi-uart-20261030/i2c-1029-a/simulation-result.json)通过，2117 笔请求逐笔核对 2112 次成功遥测及 5 次 NACK 不增计数。新增 [startup 5 场景](../results/hdmi-uart-20261030/startup-1030-a/simulation-result.json)验证等待顺序、等待期间 UART/图案继续、失败不自动重试及两种手动复位；使用真实 delayed 顶层、接口桩和缩短为 12 周期的等待参数，原冷启动计数被推进到终值，不等于真实 100 ms/PLL/I²C/图像仿真。CPU 的状态解析与原生报告审计共 105 测试通过；见 [最终日志](../results/hdmi-uart-20261030/cpu-tests-fresh-temp.log)与[执行回执](../results/hdmi-uart-20261030/verification-fresh-temp.json)。默认共享 pytest 临时目录首次触发 Windows WinError 5，保留了失败日志；不改代码、指定全新 --basetemp 后通过。模拟从机响应不是实板应答。

## 可复现入口

以下 PowerShell 命令从仓库根目录执行，使用本机 .venv/Scripts/python.exe。先生成唯一后缀；所有输出须为新文件/空目录，不能覆盖原证据。

~~~powershell
$hdmiRunStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
~~~

重放已归档的 20 秒原始字节，不访问硬件；输出放入新建的本地 build 目录：

~~~powershell
$hdmiReplayDir = "distortion/build/hdmi-uart-diagnostic/replay-$hdmiRunStamp"
New-Item -ItemType Directory -Path $hdmiReplayDir -ErrorAction Stop | Out-Null
.\.venv\Scripts\python.exe distortion/tools/hdmi_status.py --replay distortion/results/hdmi-uart-20261030/delayed-bit-1030-a/live-status-1030-b.raw.bin --output "$hdmiReplayDir/status.json"
~~~

在延迟诊断位流已下载且板卡连接不变时，重新只读接收 COM7；重新插拔后先确认 CP210x 仍为此端口，COM5/6 是下载器相关 FTDI，不能混用：

~~~powershell
.\.venv\Scripts\python.exe distortion/tools/hdmi_status.py --port COM7 --seconds 20 --output "distortion/build/hdmi-uart-diagnostic/delayed-bit-1030-a/live-$hdmiRunStamp.json"
~~~

重新审计已有原生构建，不启动 PDS；需要本机完整 build 目录，仓库中的摘要不能替代原生报告：

~~~powershell
.\.venv\Scripts\python.exe distortion/tools/audit_hdmi_uart_build.py --workdir distortion/build/hdmi-uart-diagnostic/delayed-pds-1030-a --output "distortion/build/hdmi-uart-diagnostic/delayed-pds-1030-a/audit-$hdmiRunStamp.json"
~~~

105 项 CPU 回归不访问硬件或 PDS：

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp "distortion/build/hdmi-uart-diagnostic/cpu-tests-temp-$hdmiRunStamp" distortion/tests/test_hdmi_status.py distortion/tests/test_hdmi_uart_native_audit.py
~~~

UART/I²C 数字回归依赖本机 Vivado 仿真工具；下例 kind=uart，I²C 改为 i2c 并使用另一新目录：

~~~powershell
$hdmiSimDir = "distortion/build/hdmi-uart-diagnostic/uart-$hdmiRunStamp"
New-Item -ItemType Directory -Path $hdmiSimDir -ErrorAction Stop | Out-Null
.\.venv\Scripts\python.exe distortion/tools/run_hdmi_uart_sim.py --kind uart --workdir $hdmiSimDir
~~~

延迟启动的 5 场景控制仿真也使用 Vivado；此 helper 自行创建目录，调用前该目录必须不存在：

~~~powershell
.\.venv\Scripts\python.exe distortion/tools/run_hdmi_diag_startup_sim.py --workdir "distortion/build/hdmi-uart-diagnostic/startup-$hdmiRunStamp"
~~~

仅准备新的延迟版 PDS 工程，不执行构建/下载：

~~~powershell
$hdmiBuildDir = "distortion/build/hdmi-uart-diagnostic/delayed-pds-$hdmiRunStamp"
New-Item -ItemType Directory -Path $hdmiBuildDir -ErrorAction Stop | Out-Null
.\.venv\Scripts\python.exe distortion/tools/prepare_hdmi_uart_delayed_diagnostic.py --workdir $hdmiBuildDir
~~~

实际 PDS 命令保存在新 build-plan.json 的 Command；执行时须保留原生退出码/日志和 execution.json，再审计自身报告。此准备器不生成位流、不下载硬件；不能直接复用旧程序回执、旧 STA 或旧位流准入。本轮 SRAM 具体执行脚本和哈希在已归档 program 目录 plan.json 中留档。

## 队友集成边界与下一步

我们主责 PR #10 HDMI I/O 控制与 COM7 观测；队友主责 compact-cache、DDR 和最终 STA。本轮不修改 DDR/IP、共享约束或矫正主链。主工程后续接入遥测时，65 位 cfg 元组须保留请求/确认快照；UART 必须继续由 27 MHz 驱动，不能依赖停止的 cfg/core 时钟。不得把这些独立候选的 STA 结论套用到主工程。四个既有基线的[审计日志](../results/hdmi-uart-20261030/baseline-audit.log)均通过。

供队友统一集成的[等待补丁](../../handoff/patches/hdmi-post-reset-wait.patch)与[说明](../../handoff/patches/hdmi-post-reset-wait.md)已准备，17 行新增、1 行删除，并通过 git apply --check；尚未应用到主工程。它只增加 HDMI 配置等待并改变控制器的复位连接，主工程应用后的综合、布局布线、STA 和上板仍须重新完成。

引脚：核心板 27 MHz=D18；UART TX=C24；SCL/SDA=K22/K23；KEY0=C22；公共外设复位 G25 也影响以太网 PHY。沿用 3.3V/LVCMOS33 声明；外部上拉/上升时间尚未实测，未虚构内部上拉或 IO delay。

延迟版在释放公共外设复位后等待 2,700,000 个 27 MHz 周期（标称 100 ms），才释放配置控制；不增加自动重试。当前结果足以继续准备 HDMI 信号源与显示端的受控接入，并做重复复位/冷启动对照；未完成长稳、真实输入/显示或整机畸变矫正验收。现有原始基线、延迟版数据及报告都应保留，下一次实验另存新回执。

关键 SHA256：

- control 历史 ADF：89a5f6b23bf58b9b0047d3504a54e52eb107ba4dd26a32017fe34bb335893f60。
- control 历史 .sbit：9ae5f1942d7ffff59e727e0270d3f1156515424242b2d25c79e83a2cd97150ac。
- control 原始 640 字节：d9b6479699501c27b335f9db06dbbc42be8b15c8db7076ec22517f82b1ac8176。
- delayed ADF：cad7f4cc5be50765f6eb6a14bc444938999d051aac631be6fc6d3ab50ec3e2fb。
- 当前已下载 delayed .sbit：510e14147c040d9427577405ee96eaf4d3d6be0ef70b74328445d2e3cb42bd7b。
- delayed 首次原始 640 字节：0e994981fad210b57ac6208fa76ba9331dc44f3fca5395c7607a427ab94c200a。
- delayed 追加原始 2560 字节：e0af48b3b3a1e425de1ef480216bd096dee8b6b49001e783a9499aada5610da1。
