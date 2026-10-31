# 2026-10-31 摄像头输入接入与下一步

本轮离板内部时序修复已完成：新进程双角十类检查全部0失败，功能图和17,417个FF位置不变，最小hold为+0.016ns。实际路径、PDS崩溃/规避、完整审计及接续状态见 [摄像头 DDR 时序修复记录](CAMERA_VGA_TIMING_FIX_20261031.md)。下方失败数属于保留的原始构建，不覆盖最终修复结果。开发板仍断电，无摄像头位流或实物画面。

## 当前结论与供电状态

主线已进入 **OV5640 CAM2采集 → DDR → 图像处理 → HDMI输出**。此前“先处理/输出、暂停所有输入排查”的阶段已结束；仅电脑HDMI IN / MS7200支线继续暂停。摄像头仍连接，“未接摄像头”的旧回答是用户误点，已更正。

用户最新明确将开发板断电，要求上板前通知。当前按已断电处理，不能再称板上仍运行测试图。上板前先通知用户，收到本次上电确认后才执行下载；不用历史上电反馈代替新确认。本轮仅同步本地文档，不代表Git提交或远端推送。

**DDR hold/recovery内部时序已修复；下一步核验新网表的引脚、CDC、外部接口及启动条件，准备位流，最后上板验证实时相机。** 目前没有生成或下载摄像头候选位流。此前测试图成功不能代替该候选的实物结果。

## 已完成的接入与验证

- 新顶层 distortion/board/camera_vga_output_top.v，三个camera_vga_* wrapper复用既有DVP、DDR、帧管理和处理/扫描模块；没有HDMI RX就绪前置条件。
- 目标输入640×480 RGB565，CAM2 VS/HREF低有效、低字节先到；D5为AA23。输出有效区1920×1080，图像居中，左右各640像素、上下各300像素黑边。默认畸变系数为零，先验证传输，不称当前镜头已标定。
- 32×16字节级集成仿真通过：6次提交=6次处理=6个独特显示帧，1次重复显示，1个坏帧丢弃，源/结果bank复用5/4次；3,584个扫描像素逐点匹配独立CPU参考，CRC、完整输出DE、居中黑边及排空通过。
- 实际板层控制与warmup仿真通过：8个启动、7个运行故障场景，17次复位、9次释放、4项LED和1项ready抖动检查。传感器/DDR/系统使用状态桩、warmup缩短至8ms，不代表真实SCCB或摄像头启动通过。
- 新构建准备器14项测试通过。108项独立源闭包、128个管脚（原114+CAM2的14）、71个DDR管脚及DDR实例核对通过。相机48MHz/0..5ns输入预算仍为候选约束，尚非实测AC。
- [离板验证83文件](../distortion/results/camera-vga-offline-20261031-a/manifest.json)，manifest SHA256：d448ebbb8b33407f6fd03b544453cce043626734a97ead0d563737756398ea46。

## 原生构建与未通过项

PDS从OS-temp启动Tcl时无法读取已存在的脚本；独立探针确认相同脚本在项目内成功。新准备器/执行器使用精确工作根 distortion/work/camera-vga-output，没有修改ACL；.gitignore排除该生成目录。不要重复临时目录失败调用。

构建 distortion/work/camera-vga-output/pds-20261031-a 实际完成compile、synthesize、map、place/route、STA，native exit 0，耗时672.186秒。源码、冻结副本、Tcl和执行器无漂移。STA前后最终ADF相同，SHA256：32c8aa75c766425765b7cd20bbe26dbee9f9072a069d43a297de07b3e730be3b。

**工具执行完成，但时序未通过（Some Constraints Violated）。**

| 检查 | Slow corner | Fast corner |
|---|---|---|
| Setup | 0个失败端点 | 0个失败端点 |
| Hold | 2个失败端点，最差−0.336ns | 3个失败端点，最差−0.912ns |
| Recovery | 245个失败端点，最差−4.163ns | 231个失败端点，最差−3.156ns |
| Removal | 0个失败端点 | 0个失败端点 |

失败主要涉及DDR内部保持时间与DDR/复位域恢复时间。相机域自身setup慢角+6.493ns、hold快角+0.022ns，并不证明外部相机输入时序或实物画面通过。不能照搬旧_N107 / _N173路由修复或旧端点例外到新网表，也不能用宽泛false-path消掉真实数据失败。

[原生构建摘要](../distortion/results/camera-vga-native-20261031-a/summary.json)及[70文件清单](../distortion/results/camera-vga-native-20261031-a/manifest.json)已保存。manifest SHA256：483501ecae6a0675b78a1e8f1a4b8400cba0abfe6601d9253b21285ad46c2978。大型ADF只记录原路径和hash；TimingAccepted=false、HardwareReleaseAllowed=false。

## 下一轮接续

1. 使用本候选最终ADF和双corner报告定位实际hold端点，分别审查DDR入口与PHY复位释放路径，准备有据的最小修复，保留原失败构建。
2. 对新候选补物理引脚、CDC/复位和接口检查，按变化补定向验证；既有小帧与控制仿真无差异时不重复。
3. 条件具备后生成并绑定新摄像头位流、准备新的单次SRAM计划；通知用户上电，得到新的确认后下载。现有processed_output_top成功位流只作为独立回退基线。
4. 实板先检查OV5640初始化、连续采集/处理和640×480实时画面，记录新增帧与显示刷新、颜色/丢帧/故障，再做当前镜头标定与畸变参数调整。目前没有PCLK停钟自动恢复保证。

## 历史实板基线

2026-10-31 12:33–12:35（北京时间）曾成功下载processed_output_top；用户确认红十字和彩色网格、LED6反复亮灭、LED7一直灭。它使用片内受控图，位流SHA256：0537394b548eff5035be031e8056444bad50e20e76cd4b5d49046f477ed01c72；易失SRAM、Flash未写。见[当时实板记录](PROCESSED_OUTPUT_LIVE_20261031.md)。用户本次断电后不可把该次SRAM配置视为仍运行，也不可把历史成功写成实时相机通过。
