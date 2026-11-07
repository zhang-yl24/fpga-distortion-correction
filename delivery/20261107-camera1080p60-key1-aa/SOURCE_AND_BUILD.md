# 源码与重建范围

ZIP 包含 78 份项目源码和相关约束，保留上游署名。仅为移植去掉本机路径；没有改变硬件逻辑。`native/` 是源码根，重建时需将其作为 include 搜索根。本公开路径副本没有重新综合；附带位流来自原同逻辑快照和最终 hold 优化后的实现。

本轮 AA cache 仍为 49751 字节，SHA256：

`ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088`

77 项厂商 DDR/PLL IP 输入未提供；工程持有者应使用有权使用、配置一致的输入。此包不是不依赖厂商 IP 的独立 PDS 工程，也不包含本机内部清单、ADF 或授权文件。

目标：TOP `board1080_top`，Logos2 PG2L100H、-6、FBG676，PDS 2025.2 / Fabric Compiler build 211867。实际 core 约束 125 MHz，输出 pixel clock 模型 148.5 MHz，输入 pixel clock 约束 150.2 MHz（非实测频率）。

关键配置：CORE_PRIORITY=1，INDEX_BITS=7，QUERY_DEPTH=4096，GROUP_WIDTH=64，MACRO_TILE_HEIGHT=32，RESULT_BANKS=2，STARTUP_SCAN_ALIGN=1，STARTUP_SCAN_GUARD_CYCLES=0，STARTUP_PRIME_NEXT_SOURCE=1，RATIONAL_BROWN_PROFILE=1，R34_ENABLE_GAMMA=0，STATS_ENABLE=1。

部分旧模块名和注释仍保留，例如 `camera720`、PLL“74.25 MHz”和 UART“pin pending”。实际时钟模型为输出 148.5 MHz，物理引脚为 RX=B24、TX=C24、KEY1=C23。改变 IP、PLL、参数、器件、引脚或约束后必须重新实现并检查时序，不能沿用本位流结果。
