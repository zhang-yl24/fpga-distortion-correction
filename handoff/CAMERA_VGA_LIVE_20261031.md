# 2026-10-31 摄像头候选 SRAM 下载与实屏观察

> 仓库内可移植成果：[已验证位流、下载回执及实板反馈](../distortion/results/camera-vga-upright-live-20261031-a/README.md)。下文work绝对路径为本机历史证据，不要求克隆者具备原7.7GB中间目录。

> 最新任务顺序（2026-10-31）：先推送当前成果，然后在现有640×480模式完成实际镜头畸变矫正及验收，之后再讨论清晰度和帧率。见[当前矫正任务](CAMERA_VGA_CALIBRATION_NEXT_20261031.md)。

> 最新状态（2026-10-31，用户实板反馈已确认）：新camera_vga_upright_top已于17:16:00–17:17:02成功下载至易失SRAM，位流SHA256 `e3c889f29c6fb74dda71fc49b5b6bcf2b53e9055720c18ae7238997bbe6ca1ae`、`Passed=true`、`DoneConfirmed=true`、`FlashWritten=false`、`CleanupErrors=[]`。新初始化固定3820=00/3821=06并强制读回；用户确认“已正立、左右正确，画面持续更新”“LED5/6 闪烁，LED7 一直灭”，方向修复与基础实时链路实板观察通过；见[本次用户反馈](../distortion/work/camera-vga-upright/live-observation-20261031-a.json)。旧acec0a65…b25e0的23–25fps人工计时不可归给新upright。见[本轮方向修复](CAMERA_VGA_UPRIGHT_20261031.md)、[新下载回执](../distortion/work/camera-vga-upright/program-fast-20261031-a/receipt.json)及[轻量索引c](../distortion/work/camera-vga-upright/evidence-index-20261031-c.json)。

此前用户明确回复“已上电，继续下载”后，旧camera_vga_output_top于北京时间15:38:08–15:40:06下载成功；用户确认中央相机画面随景物更新、LED5/6闪烁、LED7长灭，随后报告180°倒置。当前已由新upright替换，旧下载/反馈作为历史基线保留；新实屏方向、实时更新及LED正常已由用户确认。

## 当前硬件状态：新upright实板观察通过

- 最近一次用户上电确认在本会话有效，主任务已在此次SRAM下载前通知用户；摄像头仍为OV5640 CAM2，HDMI IN/MS7200支线保持暂停。
- 新位流 `distortion/work/camera-vga-upright/bit-fast-20261031-b/generate_bitstream/camera_vga_upright_top.sbit`，3,791,112字节，SHA256 `e3c889f29c6fb74dda71fc49b5b6bcf2b53e9055720c18ae7238997bbe6ca1ae`；最终ADF `0baea59b6633ef93278c74c00602cb2cad688d96c796458cf54243a7ab6392b5`。
- `program-fast-20261031-a/receipt.json` 记录下载成功、DONE确认、Flash未写及无清理错误；自有PID为34560、23052、32300、33976。下载计划SHA256 `a1414cb872648051d4fb89f334f20010acbc496fe8f468b4ab279af6411f8195`。
- 用户已确认新画面正立/左右正确、持续更新，LED5/6闪烁、LED7一直灭；新候选帧率、当前镜头标定、外部AC和长稳尚未验收。断电会丢失本次SRAM配置。

## 旧camera_vga_output_top下载基线（15:38–15:40）

- 开发板最近一次确认已上电，OV5640 摄像头仍连接；HDMI OUT 用于显示，电脑 HDMI IN / MS7200 支线继续暂停。
- SRAM 位流：distortion/work/camera-vga-output/bit-20261031-a/generate_bitstream/camera_vga_output_top.sbit，SHA256 acec0a6528760cabe8291d4452c635e26d7e0f7b3fdfef997a386d1c365b25e0。
- 最终 ADF SHA256 daa2a9221238d09398ba325acef561b604dcb5643571301ba8831f76736dfd9f；下载计划 SHA256 17b67e5afee9994c131c46bcd223134904505f4ee57a46f416cc0816d7fd0596。
- 唯一芯片 PG2L100H / 0x00602899，PANGO USB CABLE II，1MHz。原生 cfg_program 于 15:39:39 完成，写入耗时 30.8 秒；随后扫描 DONE=1，状态寄存器 done_i/done 均为 1。
- 仅写易失 SRAM，FlashWritten=false；本候选不包含 UART 接口。断电会丢失这次 SRAM 配置。
- 执行回执 distortion/work/camera-vga-output/program-20261031-a/receipt.json：Passed=true、DoneConfirmed=true、CleanupErrors=[]。扫描后重启自有 JTAG 服务，完整过程和日志保留。

## 旧位流用户观察与后续方向

用户对旧位流反馈“中央有相机画面，并随物体移动而更新”“56闪烁，7长灭”，随后报告“现在的图像是180度反转的”。这些是旧基础链路的实屏证据；后续新初始化与位流已完成并下载，新实屏反馈已独立确认方向修复和实时更新，记录已与上述新位流和下载回执绑定。

正常预期是黑色背景中央的 640×480 相机画面随景物变化。初始化全部就绪后还需连续 8 秒预热；默认畸变系数为零，先验证传输。LED5 是采集帧计数 bit4，LED6 是处理帧计数 bit4；两灯反复亮灭提示各自计数推进。LED7 为粘滞故障，正常预期熄灭。

方向及更新已获用户确认；下一步在当前640×480模式采集标定图、求真实参数并完成畸变矫正，保留通过的VGA基线；分辨率与帧率优化后置。处理核心cos=+1、sin=0保持，方向寄存器已由旧3820=06/3821=00改为新00/06，其他模式和字节/极性不变。用户随后询问1080p升级：当前相机640×480，原尺寸居中显示在1080p30扫描区；完整1080p像素数为当前6.75倍。现有4MiB单bank可容纳4,147,200字节的1080p RGB565帧，主要尺寸/tag静态限制满足；但传感器模式、实际PCLK、FIFO和处理吞吐需另行验证，不能承诺当前DVP链1080p30。8bit RGB565输入30fps有效数据最低124,416,000字节/秒，尚未计消隐；当前48MHz只是暂定约束，不能当作实测。最终镜头标定应绑定选定分辨率和裁剪模式。当前镜头标定、外部AC与长期稳定性仍未验收，不恢复HDMI IN支线。

## 证据入口

- [位流、检查边界与上板步骤](CAMERA_VGA_READY_20261031.md)。
- [原始下载执行回执](../distortion/work/camera-vga-output/program-20261031-a/receipt.json)。
- [本次明确上电确认](../distortion/work/camera-vga-output/live-observation-20261031-a/power-confirmation.json)。
- [本轮下载证据封存](../distortion/results/camera-vga-live-20261031-a/manifest.json)：23 个复制文件及 1 个位流本地哈希引用，全部回读/解压校验通过，manifest SHA256 9ac5aa228a321436927d483ad774b51b3b54ec650b1e2be4abf7be773348172b。精确查询确认 2072、28440、24788、2652 四个自有进程均已退出。显示/LED反馈另存camera-vga-live-observation-20261031-a；方向及分辨率反馈另存work/camera-vga-output/live-observation-20261031-a/orientation-and-resolution.json，原下载归档保持不变。
- 离板准备归档保持不变：distortion/results/camera-vga-ready-20261031-a/manifest.json，SHA256 1b0dd54bacd04831021b6cb6fb8da39e274bc88d6db9ecb2cb9e874070befc8c。其“未执行”字段是下载前快照，当前状态以本页及下载回执为准。

## 下载前旧位流人工计时：处理帧率约23–25 fps

在新upright下载前，用户测旧camera_vga_output_top的LED6从第1次亮起至第11次亮起（10完整周期）约13–14秒；LED6接processed_frames[4]，每完整周期32帧，因此320/14至320/13 = 22.86–24.62 fps，报告约23–25 fps（约24 fps）。这是旧acec0a65…b25e0在640×480下的处理完成计数人工估算，不是输入传感器实测帧率，也不是HDMI独立新帧呈现计数；HDMI仍30Hz刷新。新upright已下载但未重测帧率，不能把旧测量归到新候选。证据：work/camera-vga-upright/frame-rate-observation-20261031-a.json。
