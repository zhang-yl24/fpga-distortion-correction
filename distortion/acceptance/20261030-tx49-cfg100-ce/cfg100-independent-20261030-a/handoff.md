# CFG100 独立候选交接

本轮已完成：默认100ms边界、自然中断复位修复、新候选真实IIC两轮、同源整板compile-only。全部正式/硬件门禁保持false；板卡禁用。

- 基底与回退：TX49严格744事务/68.169s和编译DB6a838c4e...d5ce94e均未改；原B、+.191/c65、6e3及421保护输入保留。当前111角色/33加载入口，父闭包107公共源无漂移。
- 新RTL：candidate/cfg100_startup_hold.v；独立top board1080_cfg100_top.v；派生wrapper ms72xx_cfg100_ctl_reset.v；派生驱动 iic_dri_cfg100_reset.v。物理37端口保持；逆换配置块可逐字节还原母本top，rstn_out、DDR、像素/FIFO、故障排空没有延后反馈。
- 精确时序：cfgPLL名义10MHz；G25异步断言；G25/LOCK分别经cfg域2级同步观察，资格稳定后armed，再经过1,000,000完整周期才首次释放。LOCK只按同步观察值资格化，不是瞬时物理LOCK证明；放行后保持到common reset，LOCK变化不自动重置/重试。没有纯停钟检测器。
- wrapper保留旧三级释放寄存器，以effective rstn = cfg_reset_n && rstn_release立即钳低配置复位控制；reset期间done清零、SCL idle、SDA释放。旧同步状态需要恢复cfg边沿才能清，不宣称全部状态异步清零。
- 首次真实失败：boundary-a自然在SCL低时停钟并common reset，恢复后trans_en残留，8100ns Fatal；仿真原生0、host1，13.4258863s，原结果/源/日志保留。v2驱动仅模块别名和trans_en、busy两处同步reset分支；不改ACK/频率/序列/TX3199897 WAIT。厂商派生副本只供本地，不上传。
- 边界修订PASS：boundary-b，四native0/host0，21.0600626s。N1三次、N7两次、默认一次、停钟common reset三次；实际默认1,000,000×100ns=100,000,000ns。覆盖等待中/放行后重等、无cfg边沿不放行、启动LOCK低重等、释放后LOCK变化不回拉。非法N0在invalid-a正确elab1拒绝，host0，3.0442433s。
- 真实IIC PASS：wire-a，四native0/host0，51.0044082s。两epoch744事务/2294原始边沿事件；每轮49表写、row19一次、RX前导/EDID顺序、TX前导、实际START/STOP/done、完成后4RX轮询全部严格通过；每轮4,566,087配置周期。256B线级EDID重建hash仍abf91ea4...59f3da。common reset时停cfg并立即验证控制/引脚，随后新epoch重新完整等待。
- 两轮G25→首个实际IIC START均100,003,651ns（100.003651ms）；armed→release均100,000,000ns。该数字是名义配置时钟模型中的启动时序，不是实物HDMI延迟/视频FPS。
- 同源整板compile PASS：compile-a，native0/host0，47.7248302s；111角色/33成功入口实际分析并展开新hold、wrapper、reset-only driver、RXe505、TX04a9、原DDR/PLL/top。编译DB SHA256=219fab520eabdc0054ac1ba1e0f7979d456333f4c0129eb85346096ba93cf991，4,385,921B，仅frontend DB。
- 编译556警告保留：68条async_reg被忽略、276条constant-probe loop（父版275），未检出未解析依赖模式。不能据编译/相近警告数量宣称CDC或资源/时序通过。无synth/map/PNR/STA/bit，不继承旧+.064/+.191或旧资源。
- 实际入口：python -B run_boundary_v2.py（120s+30清理）；run_invalid.py；run_cfg_wire.py（300s+30清理）；run_cfg_compile.py（900s+30清理）。均已消费，目录exclusive，不能原地重跑；需要不同配置时另建候选。重型严格串行，逐次新读AC/电量，已正常退出自有进程，无超时清理。未改电源策略/GUI/网络权限/Git。
- 独立复核：a-contract-review/final-dynamic-readback.json、repair-review.json；b-closure-review/repair-closure-review.json。最初LF候选已在执行前恢复母本CRLF，快照/metadata修正保留；旧失败与旧review不重标。
- 未测/阻塞：实际LOCK/ACK/HDMI模式与冷启动、纯停钟识别、物理CDC/IO、245 DDR recovery、过热/PR14 over_temp、真实图像/长稳及新资源/最终STA。100ms不解决这些。下一独立门槛是本冻结新候选的物理诊断准入；本轮不自动启动。
