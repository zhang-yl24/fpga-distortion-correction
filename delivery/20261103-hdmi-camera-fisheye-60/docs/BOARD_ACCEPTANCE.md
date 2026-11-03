# 上板验收记录

目标为 1920×1080 每秒 60 个新校正帧，保持同学已上板 C 版的 fisheye 标定、RGB565 帧存和双线性插值。以本包 README 的最终验证状态决定是否进入上板测试。

## 工程与显示设置

输入保持 1920×1080、60 Hz，像素时钟约 148.5 MHz。输出使用输入像素时钟，扫描总尺寸为 2200×1125。KEY1 选择原图或校正，KEY0 复位。Gamma 关闭，旋转为零。源帧使用 DDR 槽 0、1、4，结果帧使用槽 2、3。

先核对候选的 BuildID、ProfileID、位流 SHA256、实际编译工具版本和布线报告。原 C 版及其已上板位流继续保留，便于对照与回退。下载记录应包含实际目标器件、位流哈希与成功状态；计时脚本读取这一记录并核对串口身份。

## 帧率统计

用独立供电冷启动后，等待输入和 DDR 正常，再分别固定原图和校正模式测量 60 秒。每次切换模式后建立新的计时窗口。使用本候选随附的接收工具，指定实际候选 BuildID：

```powershell
python tools/measure_hdmi_fisheye_fps.py --port COM7 --seconds 60 --program-receipt D:/board/program-receipt.json --build-id <candidate-plan.json中的build_id> --output D:/board/fps-60s
```

程序只读取串口。COM 口、下载记录和输出目录按同学电脑调整。安装 Python、NumPy（仿真参考）与 pyserial（串口采集）；PDS 和 XSim 分别用于硬件构建和 RTL 仿真。

需要同时记录以下独立数值：

| 指标 | 含义 |
| --- | --- |
| source_frames | 输入完整帧数 |
| captured_frames | 成功写入源槽的帧数 |
| processed_frames | 完成校正并写回的帧数 |
| unique_presented_frames | 实际显示的新帧数，作为新校正 FPS 的验收依据 |
| scan_refreshes | HDMI 扫描次数 |
| scan_repeat_frames | 重复显示旧帧次数 |
| scan_blank_frames | 无可用帧的扫描次数 |
| last_process_cycles | 最近一帧处理周期 |
| failed、fault | 故障状态及代码 |

报告同时保留 FPGA 时钟计数和主机单调时钟测得的速率。对 60.000 Hz 或 59.94 Hz 输入，先核实实际输入时钟，再与新帧率比较。稳定阶段应接近每次扫描展示一个新校正帧，重复/空白扫描和故障计数应符合预期。

## 长时间与画面检查

完成 60 秒测试后，在校正模式连续运行 600 秒，保存原始串口文件、JSON 汇总和画面录像。用棋盘格、边缘细线、运动物体检查插值、边界黑区、撕裂、局部错位及停帧；与原 C 版相同输入对照。

覆盖冷启动、处理中复位、连续模式切换、输入信号断开与恢复。每次复位后重新开始计时窗口。检查画面最后一行/最后一像素、无主 DDR 返回、CRC 错误、FIFO 欠流、重复帧比例和帧 ID 连续性。

物理签核还需要实际板卡的 HDMI 输入/输出延迟、时钟偏移和 CDC/复位检查。数字仿真结果与厂商 IP 约束审计各自作为独立证据保存。
