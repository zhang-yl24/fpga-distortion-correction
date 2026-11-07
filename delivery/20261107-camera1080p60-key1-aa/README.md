# AA 摄像头 1080p60＋KEY1 测试候选

[下载源码、位流和时序报告 ZIP](AA-camera1080p60-KEY1-public-test-20261107.zip) · [直接下载 SRAM 位流](bitstream/aa-camera1080p60-key1-1665586d.sbit?raw=1) · [测试步骤](TEST_INSTRUCTIONS.md) · [时序报告](reports/TIMING_REPORT.md) · [项目源码](native/) · [遥测工具说明](host/README.txt)

本候选供同学实板测试，**尚未验证持续 60 个新校正帧/秒、KEY1 实板切换或新画质效果**。

位流为 3791112 字节，SHA256：

`1665586da54bdbf5ed8cefa7d0bbe35f3cbb0219e03ae060fa68f6dfdb717f8a`

- PG2L100H-6 / FBG676；摄像头 1080p60 HDMI → 板 HDMI IN，显示器接 HDMI OUT。
- KEY1 默认 CORR，完整短按并释放可切 RAW／CORR；模式在源帧握手时锁存。RAW 仍走 DDR／处理链和 RGB565 量化，不是 HDMI 直通。
- **Gamma 关闭**：RATIONAL_BROWN_PROFILE=1，R34_ENABLE_GAMMA=0。STATS_ENABLE=1。
- slow/fast 两角 12 项内部时序检查零违例；最差 setup **+0.003 ns**，最差 hold **+0.044 ns**。3 ps 为很小的模型余量。
- 最终 LUT 30652、FF 26452、DRM grid 30、APM operator 70。外部 I/O、完整 CDC/reset 与实际新帧率仍待验证。

先核对 SHA 并保留现用回退，作 SRAM 临时加载。稳定 CORR 与 RAW 分开采集遥测，结合新呈现 FrameID 及硬件时间计算 fresh FPS；显示器“60 Hz”不是新帧率。回传原始串口字节、操作录像、源格式、故障和回退结果。详细步骤见 [TEST_INSTRUCTIONS.md](TEST_INSTRUCTIONS.md)。

此公开副本只含项目源码、位流、实际时序表／关键路径和测试工具，移除了本机路径及额外内部构建清单。77 项厂商 IP/PLL 输入未包含，**不是完整独立 PDS 工程**；源码路径移植边界见 [SOURCE_AND_BUILD.md](SOURCE_AND_BUILD.md)。
