# HDMI 输入接入与 SRAM 恢复（2026-10-30）

本次已把电脑 HDMI 输出接到开发板 HDMI IN；HDMI OUT 因缺线尚未接显示器。用户确认曾断电；只读 JTAG 扫描得到 DONE=0 后，重新下载**同一份 hdmi_uart_delayed_diag** 到易失 SRAM，DONE=1、未写 Flash。随后 RX/ALL 初始化完成，Windows 报告 HDMI 目标为 1920×1080、30 Hz。该候选仍无 DDR、畸变矫正主链或输入观察器，本记录不包含任何后续观察器候选结果。

[结构化汇总](../distortion/results/hdmi-input-20261030.json)与[逐文件来源/SHA256 清单](../distortion/results/hdmi-input-20261030/files.json)随仓库保存；上一轮 100 ms 等待对照见[诊断交接](../distortion/docs/HDMI_UART_BRINGUP_20261030.md)。

| 北京时间 | 原始结果 |
|---|---|
| 02:58:01–02:58:11 | COM7 只接收 10 秒，0 字节、0 包；原始未通过回执保留 |
| 02:59:47–02:59:58 | 只读 JTAG：PG2L100H、IDCODE 0x00602899、DONE=0；扫描没有执行下载 |
| 03:01:48–03:02:40 | 原 delayed 位流重新下载 SRAM，程序日志确认 DONE=1；未重新构建，未写 Flash |
| 03:03:34–03:03:44 | COM7 收到 1344 字节、21 包，序号 119–139；CRC 全通过，flags=0x003f、cfg_error=0 |
| 03:04:50–03:04:52 | Windows 只读查询发现活动 HDMI 目标 FPGA1080P30，1920×1080、30.0 Hz、74.25 MHz；查询脚本未修改显示设置 |

下载前 [JTAG 回执](../distortion/results/hdmi-input-20261030/jtag-scan/receipt.json)及[扫描日志](../distortion/results/hdmi-input-20261030/jtag-scan/scan.out.log)、[下载回执](../distortion/results/hdmi-input-20261030/program/receipt.json)及[程序日志](../distortion/results/hdmi-input-20261030/program/program.out.log)均已保留。program 目录中的 scan.out.log 是下载前扫描；下载后的 DONE=1 位于 program.out.log，不能混淆时序。

程序日志同时输出状态字 0x081ffca0，工具将 Bit 27 解码为 over_temp=1；timeout、rbcrc_err、aut_err、crc_err、id_err 均为 0。这里没有测得温度，也没有独立确认该标志的物理含义；该字段必须保留，不能把 DONE=1 解释为热状态或硬件健康验收。

## 串口与电脑显示状态

[恢复前回执](../distortion/results/hdmi-input-20261030/uart/live-before-mode-change.json)和[空原始流](../distortion/results/hdmi-input-20261030/uart/live-before-mode-change.raw.bin)没有丢弃；[恢复后回执](../distortion/results/hdmi-input-20261030/uart/live-after-program.json)与[原始 21 包](../distortion/results/hdmi-input-20261030/uart/live-after-program.raw.bin)支持本次配置结论。均为 CP210x COM7、115200/8N1，只接收，发送字节数为 0。

flags=0x003f 表示配置快照有效/新鲜、两个 FPGA PLL 锁定、RX 与 ALL 初始化完成，配置失败位为 0。成功 I²C 事务由 393,493 增至 460,698（+67,205）。[独立核验](../distortion/results/hdmi-input-20261030/uart/uart-independent-check.json)仅使用 Python 标准库 struct/zlib，从原始字节逐包核对帧头/帧尾、CRC、连续序号和全部数值字段，与接收回执一致；未访问串口或 JTAG。

解码器状态 waiting_for_digital_input_qualification **不等于本次输入失败**。该 delayed 控制诊断把 observer_released、input_qualified、像素/帧计数和宽高字段固定为 0；输入资格观测不可用。不能由这些零值判断无输入，也不能由初始化完成或 FPGA PLL 锁定推断 HDMI PHY lock、输入分辨率、实际帧率、像素正确性或画面。

[Windows HDMI 目标摘录](../distortion/results/hdmi-input-20261030/windows/hdmi-target-after-program.json)保留活动目标的原字段：FPGA1080P30、DISPLAY2、1920×1080、总时序 2200×1125、像素时钟 74.25 MHz、刷新率 30 Hz。这是电脑端配置的信号；本次查询没有改显示模式，不能替代 FPGA 端实际接收测量。摘录保留完整本地报告路径与 SHA256，省略其他显示路径；[只读查询脚本](../distortion/results/hdmi-input-20261030/windows/windows-display-readonly.ps1)一并存档。

## 离线复核与下一步

从仓库根目录重放已保存的串口流，不访问硬件；输出使用新目录：

~~~powershell
$hdmiInputStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$hdmiInputReplay = "distortion/build/hdmi-uart-diagnostic/input-replay-$hdmiInputStamp"
New-Item -ItemType Directory -Path $hdmiInputReplay -ErrorAction Stop | Out-Null
.\.venv\Scripts\python.exe distortion/tools/hdmi_status.py --replay distortion/results/hdmi-input-20261030/uart/live-after-program.raw.bin --output "$hdmiInputReplay/replay.json"
~~~

下一步接好 HDMI OUT 到显示器，核对 FPGA 自生彩条；完整输入时序/像素观测与矫正主链须各自完成验证。本次既不证明显示画面，也不构成长稳或反复冷启动验收。主工程的 100 ms 等待补丁仍按[独立补丁说明](patches/hdmi-post-reset-wait.md)统一集成并重新构建/STA。

关键 SHA256：

- 恢复到 SRAM 的原 delayed .sbit：510e14147c040d9427577405ee96eaf4d3d6be0ef70b74328445d2e3cb42bd7b。
- 恢复后原始 1344 字节：74cfae12a63516f9e23880f94c159985a3fce890ca9825f1b28c201c718ced15。
- 独立串口核验原件：e8515ba6d743cb7bae59caed225d15e6ff70dda2163af97cd3d4f55fca50e6e8。
