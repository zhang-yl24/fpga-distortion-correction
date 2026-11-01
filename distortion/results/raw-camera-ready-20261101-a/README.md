# 正立 VGA 原图采集候选：离板准备完成

本包为当前 OV5640 CAM2 镜头标定准备完整原图导出，尚未下载或取得实板原图。
开发板已断电；必须通知用户并取得新的上电确认，才能使用新会话的 SRAM 下载流程。

- 目标：`raw_camera_capture_cam2_delay`，PG2L100H / FBG676 / -6。
- 位流：[采图位流](evidence/bit-d3-a/generate_bitstream/raw_camera_capture_cam2_delay.sbit)。
- SHA256：`292b755c8bdf5f16e8697b87fc1c9ae1dbb342226404c9f647eb27030b501fa3`，3,791,112 字节。
- 最终 ADF：`6f8d2f9fd30a1f460d84b3fcc25af9075cc1cde4bf666ce66e378d5bdf85cba7`。
- fresh STA 双角十类检查及例外一致性通过；原生位流生成与读回核验完成。
- 最终 IO/CDC、128 引脚映射和 8 位输入延迟映射通过限定数字核查。
- 下载计划仅 SRAM，未执行。采图绑定仍为 pending，四项接线/下载声明全部 false。

UART 为 PGFRAME1 / 921600 baud / 640×480 RGB565_LE 原图，图像方向与已验收正立版本相同。
HDMI 预览是 720p60 扫描，将每四行/列采样得到的 160×120 图像放大；不能用显示器照片标定。
这次工作用于取得标定原图，当前还没有实际镜头 K/D 或畸变矫正画质验收。

下一步先确认 UART 实际端口，再下载本候选并验证一帧 614,400 字节原图、头/源/读回 CRC 与方向。
首帧通过后采集 6×9 内角点、25 mm 棋盘：12 个训练姿态和 6 个独立留出姿态。
每次摆好后稳定至少 10 秒，并保持到采集结束，详情见[采图会话](session/README.md)。

证据入口：[位流核验](evidence/bit-d3-a/verification.json)、
[修改范围审计](evidence/effect-a4.json)、[最终 IO/CDC](evidence/io4/io-cdc.json)、
[待执行 SRAM 计划](evidence/program-d3-a/plan.json)、
[待确认采图绑定](evidence/binding-d3-a/binding.pending.json)。

复制件保留原始字节，因此绝对路径仅对应原机。完整 ADF、厂商网表、路线和大时序报告只保留
本地路径/大小/哈希引用，本包不能独立重算完整物理证明。源码及工具在同仓库 distortion 下。
不得把历史计划和声明当作新的上电确认。外部 AC、原生电气设置、模拟 MTBF 与长期稳定性未验收。
已实板确认的显示版回退位流仍保存在 `../camera-vga-upright-live-20261031-a/`，本包没有覆盖它。
