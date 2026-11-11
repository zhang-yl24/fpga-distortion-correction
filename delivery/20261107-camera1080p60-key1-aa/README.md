# AA 摄像头 1080p60＋KEY1 测试候选

[下载源码、位流和重建工具包](AA-camera1080p60-KEY1-rebuild-kit-20261107.zip) · [直接下载 SRAM 位流](bitstream/aa-camera1080p60-key1-1665586d.sbit?raw=1) · [测试步骤](TEST_INSTRUCTIONS.md) · [时序报告](reports/TIMING_REPORT.md) · [项目源码](native/) · [遥测工具说明](host/README.txt)

[新增显式串口采集与新帧率分析](host/LIVE_CAPTURE_ZH.md)：可顺序采集原始字节、保存请求身份并按硬件 tick 分析稳定 RAW／CORR 窗口；现支持同一 epoch 的 600 秒等持续记录，逐窗累计、流式校验，单次最多 1 小时。该主机增强独立于原始冻结 ZIP，尚未连接真实串口验证，不改变位流或 RTL。

本候选供同学实板测试，**尚未验证持续 60 个新校正帧/秒、KEY1 实板切换或新画质效果**。

位流为 3791112 字节，SHA256：

`1665586da54bdbf5ed8cefa7d0bbe35f3cbb0219e03ae060fa68f6dfdb717f8a`

- PG2L100H-6 / FBG676；摄像头 1080p60 HDMI → 板 HDMI IN，显示器接 HDMI OUT。
- KEY1 默认 CORR，完整短按并释放可切 RAW／CORR；模式在源帧握手时锁存。RAW 仍走 DDR／处理链和 RGB565 量化，不是 HDMI 直通。
- **Gamma 关闭**：RATIONAL_BROWN_PROFILE=1，R34_ENABLE_GAMMA=0。STATS_ENABLE=1。
- slow/fast 两角 12 项内部时序检查零违例；最差 setup **+0.003 ns**，最差 hold **+0.044 ns**。3 ps 为很小的模型余量。
- 最终 LUT 30652、FF 26452、DRM grid 30、APM operator 70。外部 I/O、完整 CDC/reset 与实际新帧率仍待验证。

先核对 SHA 并保留现用回退，作 SRAM 临时加载。稳定 CORR 与 RAW 分开采集遥测，结合新呈现 FrameID 及硬件时间计算 fresh FPS；显示器“60 Hz”不是新帧率。回传原始串口字节、操作录像、源格式、故障和回退结果。详细步骤见 [TEST_INSTRUCTIONS.md](TEST_INSTRUCTIONS.md)。

**直接测试**使用现成位流即可。**从源码重建**请按 [重建入口](rebuild/README.md)、[IP／PLL 获取与生成步骤](ip_setup/IP_REGENERATION_STEPS.txt)、[配置工具说明](ip_setup/CONFIG_TOOLS_README.txt)补齐有权使用的厂商输入，再串行运行 Map、place、route／hold、独立 STA 和 bitgen。

包中已补齐 371 项 DDR 参数、两 PLL 参数、参数写入／核对工具、155 文件相对闭包清单、68 导入及五阶段 Tcl。匹配原版 IP 补齐后的静态闭包已检查通过；全新 GUI 生成及重新 EDA 尚未实跑，不能承诺重建得到相同位流字节或 3 ps 余量。

此公开副本不含受限厂商 RTL、许可证、本机路径或额外内部构建记录。77 项厂商 IP/PLL 输入仍须从合法官方组件生成／恢复，**不是免依赖的独立工程**；完整边界见 [SOURCE_AND_BUILD.md](SOURCE_AND_BUILD.md)。


[新增独立资源研究候选 AE / AF54](../../research/aa-cache-resources/README.md)：AF54 的实际 query FIFO 声明宽度从 63 位降至 54 位，已过真实 cache 参数的离板差分；AE 另有单表达式重复检测证据。两者均未运行 Map/STA 或实板，不能直接烧板，也不替换本页冻结 AA 源码、位流或 3 ps 时序结果。

[新增三结果缓冲源码研究](../../research/aa-elastic-result-buffer/README.md)：通用入口默认关闭，可由独立原生入口显式选择 ENABLE_ELASTIC_BUFFER=1、RESULT_BANKS=3。离板模型覆盖连续处理、扫描交接和归一化摄像头采集链；这不是物理 HDMI、DDR 或实板验收。本研究没有新 PDS/Map/STA、资源结果或位流，不可直接烧板，也不替换本页冻结候选。
