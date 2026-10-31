# 2026-10-31 处理/输出诊断位流与上板准备

**后续已上板成功：** 用户确认上电后执行 `program-20261031-a`，DONE=1、Flash未写；用户确认红十字和彩色网格上屏、LED6反复亮灭、LED7熄灭。见[最新实板结果](PROCESSED_OUTPUT_LIVE_20261031.md)。下面“断电/等待上电/尚未下载”描述准备阶段，不再是当前状态；已使用的计划不得重复执行。

本记录接续 [内部时序修复](PROCESSED_OUTPUT_TIMING_FIX_20261031.md)。目标仍是摄像头画面经处理后 HDMI 输出；当前用片内受控图像验证 DDR、矫正和显示链，物理输入排查暂停。摄像头仍连接，早先“未接摄像头”是误点。

用户最新报告开发板已断电，要求上板时通知。本轮没有连接板卡、JTAG 或 UART，没有下载或写 Flash；旧 SRAM 彩条配置已经丢失。准备完成后通知用户上电，收到上电反馈再执行下面的 SRAM 计划。

## 已生成的确切候选

- 顶层：`processed_output_top`，片内棋盘/网格 → 真实 DMA/CDC/写仲裁 → 源 DDR → 生产 bank manager/rowpipe 矫正 → 结果 DDR → 读帧/FIFO/扫描 → 独立 MS7210。
- 最终 ADF：`distortion/build/processed-output/physical-final-report-20261031-a/input.adf`，SHA256 `1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b`。
- 位流：[processed_output_top.sbit](../distortion/build/processed-output/bit-20261031-b/generate_bitstream/processed_output_top.sbit)，3,791,112 字节，SHA256 `0537394b548eff5035be031e8056444bad50e20e76cd4b5d49046f477ed01c72`。
- 原生生成工具：PDS 2023.2-SP3 build 154097；器件 Logos2-PG2L100H--6-FBG676。
- 位流目录 [verification.json](../distortion/build/processed-output/bit-20261031-b/verification.json) 与执行回执保存源闭包、ADF、原生 STA、运行时门禁和生成文件的绑定。实际顺序是 STA 完成、十类检查及精确例外校验通过、随后生成位流；未重跑综合/布局布线。

双角十类内部检查均零失败：slow/fast setup +0.286/+2.924ns，hold +0.136/+0.099ns，recovery +1.751/+4.039ns，removal +0.311/+0.158ns，MPW +0.035/+0.035ns。5 条精确复位约束及唯一 `_N107` 路由修复的完整依据仍在上一份交接与原封存中。

第一次 `bit-20261031-a` 在 STA 通过后因 P:/ 与 D:/ 路径别名比较失败，未进入位流生成。工具统一解析实际路径后，新的 `bit-20261031-b` 成功。失败目录与原始回执保留；不能把第一次工具问题写成设计时序失败。

## CDC 与 HDMI OUT 的核验范围

[CDC 结构记录](../distortion/build/processed-output/cdc-structural-20261031-c.json) 核对 34 位 Gray、19 条标量同步链，共 106 个 FF；全部 Gray 两级同 BLE、首级只驱动次级，双角最大到达 0.966ns。另核对 7 条复位同步链与 core 域 28 个第二级复位副本。每角 1504 条报告中的 max-delay/setup 路径均通过，最大到达 7.109ns；mailbox 保持到返回确认的条件按实际 RTL 核对。这是当前限定结构和报告的证据，不是全设计 CDC/MTBF 证明。

三条非同 site 标量链已补 [原生级间路径审计](../distortion/build/processed-output/cdc-interstage-20261031-a.json)：DDR ready、System failed、Processed bit 的双角 setup/hold 共 12 条路径均通过。37.037ns 周期下，最大 FF 时钟至目标 LUT 输入延迟 1.609ns，最小 setup 裕量 35.165ns，最小 hold 裕量 0.400ns。结构报告中的“级间路径待补”由此独立附件完成，原报告不改；这些数值仍不构成模拟亚稳态概率证明。

[TX 332 条原生查询分析](../distortion/build/processed-output/tx-delay-analysis-20261031-a.json) 覆盖 27 个数据/控制口及转发时钟、slow/fast、min/max、rise/fall。数据路径分段以同一个 PLL 节点和确切 FF CLK 边界组合；没有混用正常报告的 max 值充当 hold 最小值。49 项 TX 设置与已有厂商表同序一致，配置 `1281=04` 的采样位含义仍未确认。

以下窗口是条件计算，外部 skew 定义为“数据封装/PCB 延迟减去时钟封装/PCB 延迟”：

| 假设 | 允许外部 skew | 限制 |
|---|---|---|
| 上升沿采样前一像素 | −1.066 至 +7.918ns | 使用资料中的 setup 0.879ns、hold 0.220ns；实际模式及 PCB skew 未证实 |
| 下降沿采样当前像素，0.4–0.6 周期相位 | −6.412 至 −0.434ns | 仅为情景假设；零 skew 不在窗口内，不能宣称该情景通过 |

因此 `ExternalTimingAccepted=false` 保留；不添加猜测的 output-delay，也不把诊断试显等同外部 AC 签核。管脚、电压和驱动方向仍对应已核对的 114 个实际 pad。可逆 SRAM 试显用于取得真实显示证据。

## 上板执行与预期画面

已准备的计划目录为 `distortion/build/processed-output/program-20261031-a`，固定 PG2L100H / `0x00602899`、USB Cable II、1MHz、易失 SRAM。默认命令只做离板验证：

```powershell
.venv/Scripts/python.exe distortion/tools/execute_processed_output_program.py --plan distortion/build/processed-output/program-20261031-a/plan.json
```

用户确认上电后，根代理在同一命令末尾加 `--execute --board-powered`。执行器先检查完整绑定和精确设备身份，再用自有 JTAG 服务下载并检查 DONE；只清理自己创建的进程。每个计划只允许执行一次，失败后保留回执并重新准备计划。DONE 仅证明配置成功，显示和处理帧进展另行检查。

上电时保持开发板电源、下载器和 HDMI OUT 显示器连接即可；摄像头和 HDMI IN 接线无需调整。本顶层没有 UART 诊断接口，旧 COM7/PGHDMI01 解码器不适用，不要求接 UART。

[CPU 期望处理图](../distortion/results/processed-output-preview-20261031/processed-reference.png) 是带红十字、绿色网格及弯曲边界的渐变棋盘，四周有黑色区域。它不是实板截图。原图 CRC `C58CBE14` 与原生全尺寸受控源测试一致；CPU 矫正结果 CRC `46CDDAE1`，2145 个坐标完成独立标量/向量交叉核验。原有小尺寸真实 System 集成 9 个帧 ID、14 次重复等数字证据直接复用，没有无因重跑。

候选为 1920×1080，输出刷新 30Hz；片内 27MHz 源约 10.91 个新帧/秒，Gamma 旁路，Brown 参数是压力模型。不能把这次试显写成实时摄像头、当前镜头标定或每秒 30 个新帧已通过。

上板先确认是否出现该处理图及有无黑屏、花屏，再结合顶层状态灯判断进展。`led[7:0]` 依次为失败、处理帧 bit4、流水线放行、源帧 bit4、TX 初始化完成、视频 PLL 锁定、DDR 就绪、心跳。[厂商硬件手册文本](../hardware_check/hardware-guide.txt)第2199行说明高电平点亮，8个LED脚与本候选FDC逐项一致。因此正常为LED1/2/3/5常亮、LED7灭，LED0每0.5秒翻转、LED4约每1.47秒翻转、LED6每16个处理完成翻转。

图像RGB仅依赖坐标，不含动态帧号；画面静止是预期，不能据此判断停帧，也不能单靠静态图证明新帧持续处理。LED6连续变化可说明处理帧计数推进，仍不直接证明每个新帧都被显示。

## 自动检查与封存

本轮 root 实际运行 62 项 CPU 检查全部通过：位流 16、CDC 结构 11、TX 延迟 6、SRAM 执行器 24、级间路径解析 5。执行器测试使用模拟服务，不连接硬件。9 个新增/相关 Python 工具语法检查与 `git diff --check` 通过；原生查询全部退出，临时 P: 映射已清理。没有重新运行已通过且相关 RTL 未变的长仿真。

新封存位于 [processed-output-ready-20261031-b/manifest.json](../distortion/results/processed-output-ready-20261031-b/manifest.json)，包含失败和成功位流生成回执、有限 CDC/TX 报告、原生查询、工具/测试、CPU 期望图及未执行的 SRAM 计划；ADF、厂商网表与位流仅保存本地哈希引用。151 项初始封存和 163 项时序修复封存保持不变。首次 `processed-output-ready-20261031` 因 Windows 深层路径长度限制仅留下部分副本，没有 manifest，不是有效成果封存；新工具将过长路径转换为短文件名，并在 manifest 保存完整原路径。

最终封存 113 个文件、18 项本地引用，逐项回读和解压校验通过；manifest SHA256 `0ae7b30b4225becc45798019da062484d676909d4ddc1c85739b104e769b3689`。准备工作已完成，当前等待用户收到通知后上电；没有设备扫描或下载结果。
