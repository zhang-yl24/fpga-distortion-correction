# 固定纯校正测量版

已完成 Map、配对 PNR、独立双角 STA、同数据库 bitgen。今晚未访问开发板。

- 位流：`frozen/fixedpure-pgstat02-diagnostic.sbit`
- SHA256：`57044fe803d9880f016b53c91234def946bb13da6cc1d357cd15689a5212a374`
- 最终 ADF SHA256：`2ae7f0e6eb5d16938d4d9ad16dfa592c2bed0dd073c3e622f188432d59c33dff`
- 固定 correction=1、Gamma=0，原旋转参数；轻量 PGSTAT02，未启用 PGFRAME。
- 输入仍为已验证的电脑 HDMI 1920×1080@29.97/30；不是已完成的 60Hz profile。
- 实际构建和剩余时序：`RESULT_BRIEF.json`。慢角 setup38 / −0.314ns，未最终签核。

明早连接确认后，复用既有易失配置、器件身份、实温监测及休息回退流程；先保存实际加载回执与本位流 SHA。完整数据保留为原始 UART 字节，绑定输入、参数、位流和源清单。

已准备 `host/canonical-requests/PLAN.json` 及三个命令文件：一次 SGA1、两次 SGT1。先收匹配 ARMED ACK 和 mode1 的完整 PGSIG，再收第一次 PGSTAT02；在同一无复位 epoch 中观察约20秒后请求第二次 PGSTAT02。两次快照都须 last_valid、mode1、正确参数ID、ticket/nonce 和 CRC。此文档和命令均未执行串口。

现有v2把RX广播给两个parser，嵌入对方magic的任意载荷仍有混流限制。这里保留原实现，只绑定已逐字检查、在无空隙字节模型中使两个parser均回到idle的确切命令。没有通过等待来宣称协议已修复。新通用RX路由补丁未纳入，本轮HDL验证被审批拒绝，状态仍为 NOT_RUN。

离线分析入口为 `host/pure_window.py`，读取实际原始字节与 `MEASUREMENT_BUILD_MANIFEST.json`，并要求真实无复位 epoch 证明。窗口限制来自现有工具的32位差值校验，20秒小于34.36秒。

处理吞吐使用 `Δprocessed_frames / (Δcore_tick / 125000000)`；内部最后一帧接受至成功边沿距离为 `(last_process_cycles_legacy+1)/125000000`。窗口tick差不加1。scan刷新、重复显示和新处理帧分开；UART主机耗时、PGSIG八点样本都不构成外部端到端延迟或完整画质证据。当前硬件fps、内部实测周期、外部E2E均未测。

Penn参数来源已经核验；它不自动构成新摄像头镜头的标定。`MEASUREMENT_BUILD_MANIFEST.json` 的实际输入素材身份仍待本次板测绑定。
