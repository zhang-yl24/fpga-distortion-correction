# Board1080 HDMI 外部 I/O 时序证据（2026-10-29）

## 结论与范围

本次只核查源码、约束和本地原始手册，未运行 EDA、未访问开发板。现有简版 MS7200/MS7210 datasheet 能证明支持 RGB444 24-bit SDR/DDR 和直流电气条件，不能提供当前工程所需的外部 AC 时序数值或已配置的采样边沿。不能据此填写可信的 `set_input_delay` / `set_output_delay`，也不能将外部 I/O 的 unconstrained 提示解释为物理时序验收通过。

现有诊断 FDC 开头明确声明外部 I/O delay 故意留空；第 6–7 行仍残留旧的“下方有 provisional half-period delays”说明，与实际约束不一致，应在维护约束时清理说明。不能用半周期估计、零延迟或 blanket false path 消除这项证据缺口。

## 原始资料

以下页码均按 PDF 文件从第 1 页计数。路径以仓库根目录为基准。

1. RX：`vendor/board/盘古100Pro+开发板（MES2L676-100HP）配套资料/4_IC_datasheet/HDMI PHY/《MS7200 Datasheet-EN》(1).pdf`，15 页。第 2 页列出 SDR/DDR、24-bit RGB/YUV444；第 6 页 Table 2 是数字输出格式表；第 11–12 页是绝对额定/直流参数。未找到 data、DE、HS、VS 相对 PCLK 的 tCO(min/max)、SDR 有效边沿、PCLK 反相寄存器及 bit 定义。
2. TX：`vendor/board/盘古100Pro+开发板（MES2L676-100HP）配套资料/4_IC_datasheet/HDMI PHY/《MS7210 Datasheet-CN》-sp(1).pdf`，14 页。第 2 页列出 SDR/DDR、24-bit RGB/YUV444；第 6 页表 1 是数字输入格式表；第 9–10 页描述 PCLK/数据/控制脚；第 11 页为绝对额定/直流参数。未找到 TX 输入 tSU/tH、SDR 有效采样边沿、PCLK 相位/反相寄存器定义及对应模式的 AC 测试条件。
3. `vendor/board/hardware-guide.pdf`，V1.2 手册。第 45 页说明 MS7200 SA 接地、8-bit IIC 写地址为 `0x56`；第 47 页说明 MS7210 SA 拉高、地址为 `0xB2`；第 45、48 页起有接口引脚表。实物 BASE V1.4 与本地 V1.2 资料的一致性仍需确认；缺当前板修订版 data/control 与 PCLK 的传播延迟及最坏偏斜。

两芯片第 6 页表格的列为 480P、720P、1080P、4K，没有给出各列帧率。不能仅凭表内“1080P / 148.5 MHz SDR / 74.25 MHz DDR”就断言本工程的 1080p30 应使用 DDR，或证明当前 SDR 配置正确。具体格式须由寄存器定义、输入源模式和读回证据确认。

`hardware_check/ms7210.txt` 是已有的派生文本，本文以 PDF 原件为准；RX 第 12 页、TX 第 6/11 页还做了页面图像核对，未发现文本提取漏掉的 AC 表。

## 当前源码实现

- `distortion/board/board1080_rowpipe_top.v`：RGB888 输入接入采集系统；输出 `pix_clk` 直接来自 `video_pll`，顶层没有单独的输出时钟反相；配置时钟来自 `configuration_pll`。
- `distortion/rtl/experimental/hdmi1080_capture_cdc.v` 在输入 PCLK 上升沿采集；`distortion/rtl/experimental/ddr_video_output_1080_board.v` 在输出时钟上升沿更新像素和 HS/VS/DE。这仅说明 FPGA 的动作，不能证明 PHY 的收发边沿正确。
- `distortion/board/board1080-cdc-reset-diagnostic.fdc`：输入 PCLK 的 STA 包络为 75.1 MHz，周期 13.315579 ns；输出时钟为 27 MHz × 11/4 = 74.25 MHz；配置时钟为 27 MHz × 10/27 = 10 MHz。无有效 external input/output delay 约束。
- 视频参数 1920×1080、总时序 2200×1125、74.25 MHz 对应设计值 30 fps。这是参数计算，不是实测帧率或 PHY 模式验收。
- `distortion/platform/video_base/source/hdmi/ms72xx_ctl.v` 使用 RX `0x56`、TX `0xB2`，先初始化 RX 再初始化 TX；IIC 参数为 10 MHz / 400 kHz、2-byte 寄存器地址、1-byte 数据。
- 实际初始化表在同目录 `ms7200_ctl.v` 与 `ms7210_ctl.v`。例如 RX 表有 `0204=02`、`0205=40`，TX 表有 `1281=04`、`0016=04`；本地简版手册未定义相应模式/边沿 bit，不能凭写入数值推断含义。
- 同目录 `iic_dri.v` 的 S_ACK 状态约第 438 行为 `if(dsu)// & sda_in)`，状态推进没有检查从机 ACK。现有 `init_over` 只能证明控制序列结束，不能证明 PHY 收到全部配置或已锁定。此项应由 HDMI 启动修复独立处理；本次未改 RTL。

## 缺失参数与可执行的下一步

需要芯片详细 programming guide / register map：RGB444 24-bit SDR 选择、PCLK 边沿/反相、复位默认值、锁定/模式状态寄存器和读回掩码。还需要实际电压/负载/温度工艺条件下 RX 的 tCO(min/max)、TX 的 tSU/tH、PCLK 占空比和抖动限制，以及 BASE V1.4 和连接板 data/control 对 PCLK 的最坏传播延迟偏斜。封装管脚表不能替代走线延迟。

可直接向资料提供方询问：“请提供 MS7200 输出与 MS7210 输入在 3.3 V、RGB888 SDR、74.25 MHz 下的有效 PCLK 边沿、tCO(min/max)、tSU/tH、时钟容差/负载条件及模式控制寄存器定义；同时需要 MES2L676-100HP BASE V1.4 的 HDMI 并行总线与 PCLK 走线偏斜资料。”3.3 V 来自当前工程 LVCMOS33 约束，仍须与实际 I/O 供电核对。

现在可以离线推进：

1. 固定候选源码/约束哈希，维持外部 AC 未验收标记，不为清理告警填写假定数值。
2. 完善 IIC ACK、超时、错误状态与失败回归；取得寄存器定义后增加模式读回，将初始化结束、配置成功和输入锁定分别呈现。
3. 做 SDR 路径端到端 RTL 仿真和模式监测，验证帧尺寸、节拍、CDC 数字行为；该结果不替代 PHY 边沿关系和实际板级裕量。
4. 参数齐备后按明确的参考边沿及 min/max 定义建立 source-synchronous I/O 约束，检查最大/最小时序和外部端点。先验证边沿关系，再评估是否需要调整输出转发时钟相位。

## 本次审查时的 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| MS7200 原始 PDF（完整路径见上文） | `3ffeecfdb4e6741d369b7b6d89d118ca8cf2bcfd617fd7ea3f21f1798fbf5207` |
| MS7210 原始 PDF（完整路径见上文） | `2e9ea30aaf970a5b53a6f9d71185959a8145df45f1ef0d516b77e13f6c5d25f3` |
| `vendor/board/hardware-guide.pdf` | `f2fb07625a0a31705d7e8477308f7bcb1aa5272b6b0754cfbf9daca20ebec114` |
| `hardware_check/ms7210.txt` | `6550e729e11558e12d23e8e516cecd390ef504077287e7add61efba9016298a7` |
| `distortion/board/board1080_rowpipe_top.v` | `28cba7652a01f4eaef7f7edbc19ff63b12176aaa355c13e68a6d74bf2905d6da` |
| `distortion/board/board1080-cdc-reset-diagnostic.fdc` | `2ff6dd8510e7b0566f550143561ac4138c19cd255944811b4561979f6e8b0f23` |
| `distortion/platform/video_base/source/hdmi/ms72xx_ctl.v` | `df3876bc1a3bf3a7efe7adeed56b2f9625af4ac9ba56074925671f49751cf69a` |
| `distortion/platform/video_base/source/hdmi/ms7200_ctl.v` | `501521c4cceecd48de5741d3116eb7062c93a70a606a386682e1d8756a494199` |
| `distortion/platform/video_base/source/hdmi/ms7210_ctl.v` | `c9b101e58f381ddf3c6d663d0003c18065302659424b8345022161413ccf09ae` |
| `distortion/platform/video_base/source/hdmi/iic_dri.v` | `5f60bc8bcac110f0125a278c332065d2594874c465ec961c603662f92c16b13e` |

这些哈希用于定位已审查的源文件，不表示整套构建、时序报告或下载文件已经验证。
