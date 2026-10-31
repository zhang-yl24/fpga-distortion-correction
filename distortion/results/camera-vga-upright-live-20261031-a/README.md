# OV5640 VGA upright 实板交付快照（2026-10-31）

本目录保存已经生成、验证并下载的 camera_vga_upright_top 位流，以及下载后的用户实板确认。源码、测试和工具位于同仓库的 distortion/board、distortion/rtl、distortion/tools 和 distortion/tests；本目录不复制大型原生数据库或网表。

当前位流：[camera_vga_upright_top.sbit](evidence/bit-fast-20261031-b/generate_bitstream/camera_vga_upright_top.sbit)

- 器件：Logos2 PG2L100H，-6，FBG676；OV5640 CAM2，HDMI OUT。
- 位流 SHA256：e3c889f29c6fb74dda71fc49b5b6bcf2b53e9055720c18ae7238997bbe6ca1ae，3,791,112 字节。
- 2026-10-31 北京时间 17:16–17:17 下载到易失 SRAM，DONE 确认、Flash 未写、清理无错误。
- 用户确认：画面已正立、左右正确且持续更新，LED5/6 闪烁，LED7 一直灭。
- 有效相机图像仍为 640×480，置于 1920×1080、30 Hz 输出扫描区内。1080p 输出信号不代表相机已采集 1080p。
- 当前畸变系数为零，尚未完成当前镜头的真实畸变校正。旧 camera_vga_output_top 的 LED6 人工计时约 23–25 fps 仅适用于该旧位流；新 upright 未重测精确帧率。

## 最新任务顺序

用户在本次推送前明确要求：先保存当前成果，然后先在当前 640×480 模式实现实际镜头畸变校正；清晰度和帧率升级后置。旧观察 JSON 或证据索引内“下一步 1080p”的文字是当时快照，不覆盖这条最新指示。

后续先取得与当前传感器模式、裁剪和方向一致的原图与标定数据，验证真实参数及定点实现，再上板检查校正画质。保留本位流作为已确认的 VGA 回退基线。

## 可移植证据入口

- [用户实板观察](evidence/live-observation-20261031-a.json)
- [SRAM 下载回执](evidence/program-fast-20261031-a/receipt.json)
- [位流验证回执](evidence/bit-fast-20261031-b/verification.json)
- [SCCB 仿真](evidence/sim-20261031-b/upright-simulation.json)
- [复位与单分支布线效果审计](evidence/reset-effect-20261031-a.json)
- [最终 IO/CDC 审计](evidence/io-cdc-native-final-20261031-a/io-cdc-native-proof.json)
- [逐文件哈希清单](manifest.json)

复制证据保持原字节不变，因此其中的 Windows 绝对路径、work 目录、工具哈希和执行授权字段只描述原机器上的历史执行。克隆仓库不会自动恢复原机完整工作目录，也不能把历史上电确认或历史执行计划视作新的硬件操作授权。需要重新下载时，应先验证位流与器件，并为当前机器/会话生成和复核新计划。

完整 ADF、厂商功能网表和大型 STA 报告只在 manifest 的 LocalReferences 中记录原路径、大小及哈希；本包不声称仅靠这些小型回执就能独立重算全部物理证明。原始位流生成前的完整审计已执行，当前提交保存其结果及可使用位流。外部 AC、模拟 MTBF、长期稳定性和真实镜头校正画质仍属于未完成验证。

本包为只读整理，未修改冻结来源文件，未执行 PDS、Git 或硬件操作。
