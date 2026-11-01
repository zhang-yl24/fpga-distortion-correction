# FPGA 实时图像畸变矫正

当前已完成 **OV5640 CAM2 → 640×480 实际镜头畸变矫正 → HDMI 显示**。用户实板确认画面持续更新、直线明显变直，LED5/6闪烁、LED7常灭；LED6十完整周期13–14秒，处理完成帧率人工估算 **22.9–24.6 fps（约24 fps）**。HDMI 1080p30仅为扫描格式，不代表有效相机分辨率或每秒显示30张新图。

当前镜头使用12张训练、6张独立验证完成标定；两帧真实原图的614400个RTL输出像素匹配独立整数参考，原生双角十类时序和限定IO/CDC检查通过。右下物理遮挡区未光学验收，人工帧率观察不替代精确性能或长期稳定测量。

- [当前矫正位流、来源快照与离线验收](distortion/results/calibrated-camera-ready-20261101-a/README.md)
- [SRAM实际下载与DONE回执](distortion/results/calibrated-camera-download-20261101-a/README.md)
- [用户实屏矫正反馈](distortion/results/calibrated-camera-live-20261101-a/README.md)和[当前帧率测量](distortion/results/calibrated-camera-frame-rate-20261101-a/README.md)
- [标定与完整开发交接](handoff/CAMERA_VGA_CALIBRATED_BUILD_20261101.md)

**下一阶段按用户指定：先把有效相机与矫正图像提升到1280×720，再在720p基础上提升帧率。** 独立分支`codex/camera720-output`已实现720p单位映射运输候选，完整数字链路两帧共1843200个HDMI像素核对通过；尚未完成720p镜头矫正参数、最终物理检查或上板验证。见[720p实现交接](handoff/CAMERA_720P_IMPLEMENTATION_20261101.md)及[离线阶段证据](distortion/results/camera720-offline-20261101-a/README.md)。HDMI IN/MS7200支线继续暂停。已验收的VGA源码与位流保留用于回退，断电后需重新下载易失SRAM。

下文保留历史阶段，不覆盖以上当前结果。私人现场相机像素和大型构建中间文件留在本机；封存包提供来源和哈希引用。

盘古676 / PG2L100H-6IFBG676项目。三人轮流推进的私有协作仓库。

**先阅读 [交接说明](handoff/交接说明.md) 和 [当前交接点](handoff/CURRENT.md)。**

## 历史阶段：摄像头接入候选与此前断电

主线是 **OV5640 CAM2摄像头 → DDR/图像处理 → HDMI显示**。已开始摄像头输入适配，仅电脑HDMI IN / MS7200支线继续暂停。摄像头仍连接；此前“没有接摄像头”为误点，已更正。

**历史记录：用户当时通知开发板断电，随后已上电并完成新版本实板确认；当前状态见顶部。** 旧processed_output_top测试图曾显示成功，但易失SRAM状态不能描述为当前仍运行。此次仅同步本地文档，不代表Git提交或远端推送。

新camera_vga_output_top目标640×480 RGB565、1080p30居中输出，默认零畸变系数先验证传输。小帧DVP仿真6帧、3,584像素及板层启动/故障控制仿真通过；原生compile/synth/map/pnr/STA完整完成，但**DDR hold/recovery时序未通过**。slow/fast hold最差−0.336/−0.912ns，recovery最差−4.163/−3.156ns，两角setup/removal零失败。尚未生成或下载摄像头位流。

下一步先处理新候选时序并完成引脚/CDC/复位与接口检查，再准备位流→通知上电→验证实时画面→调整当前镜头标定和畸变参数。旧候选的时序修复或测试图实板成功不能直接作为新摄像头验收。

依据：[摄像头接入交接](handoff/CAMERA_VGA_INPUT_20261031.md)、[原生构建摘要](distortion/results/camera-vga-native-20261031-a/summary.json)。目标分辨率/输出刷新不等于已实测相机帧率。新候选无UART接口，不沿用旧COM7/PGHDMI01命令。

## 历史进展

以下记录保留各日期、各候选及各测试环境的事实，不覆盖2026-10-31的最新方向。相机图像、HDMI IN诊断、合成测试和RTL回放分别说明来源，历史帧率不作为当前工程的实板验收。

2026-10-30 00:30–00:52（接入 HDMI 信号前的历史对照）：100 ms 等待版恢复 I²C 应答，两次共 50 个 CRC 正确包、配置错误为 0，但当时 RX/TX 尚未初始化。后续初始化与输入失败记录见[当前交接点的历史段](handoff/CURRENT.md)；旧 [诊断说明](distortion/docs/HDMI_UART_BRINGUP_20261030.md)、[结果与证据包哈希](distortion/results/hdmi-uart-20261030.json)保留。

2026-10-29：已从修复后的最终 ADF 生成离线 `.sbit`，并在生成前执行原生时序/例外审计；实际 rowpipe 板级控制回归也已通过。未访问开发板，实物 HDMI/DDR/相机验收仍待完成。见[离线进展与下一步](handoff/BOARD1080_OFFLINE_NEXT_20261029.md)。

2026-10-29：DDR 定向时序修复候选已在同一已布线副本中通过 PDS 双角十类原生报告审计。局部 `_N173` 数据支路绕行消除 slow/fast hold 失败；精确 IP 复位例外覆盖244项内部检查及1项入口RDC，setup/hold false-path保持为空。结果仍是离板候选，外部 IO、CDC、DDR训练和实板验收未完成。详见 [DDR 时序修复](handoff/BOARD1080_DDR_TIMING_FIX_20261029.md)。

2026-10-28（修复前历史基线）：rowpipe已接入1080P整链，新源八帧16588800像素/CRC及稳态30.000fps数字回归通过；逐帧处理周期未下降，未声称提速或实板fps。PDS2023.2完整流程当时有每角1项PHY hold及slow245/fast234项recovery。修复后离板候选见[DDR时序修复](handoff/BOARD1080_DDR_TIMING_FIX_20261029.md)。

2026-10-28：新源1080八帧离线数字链路通过；此行记录修复前复位/RCF物理诊断，修复后状态见当前交接点。

2026-10-25：新模组CAM2已取得真实640×480原图与内部彩条，七项受限控制实板测试通过；另一眼读到OV5640 ID，但启用数据输出后的SCCB读取失败，尚未采图。完整720p帧的下游数字仿真通过，传感器720p模式仍待解决时钟资料矛盾。实际视场、标定、画质、双目同步和新镜头性能分别验收；按任务推进，11月4日前完成提交。

- [持续开发成果与实际图像](distortion/output/project/持续开发成果-20261025.md)
- [开灯后房间原图与补采结果](distortion/output/project/开灯后原始采集-20261025.md)
- [CAM1单变量诊断与最新计划调整](distortion/output/project/CAM1单变量诊断与计划更新-20261025.md)
- [重新上电与复位隔离的最新结果](distortion/output/project/重新上电与复位隔离复查-20261025.md)
- [FPC插紧后的复测与诊断推进](distortion/output/project/FPC插紧后复测与诊断推进-20261025.md)
- [10月26日新事务诊断实板结果](distortion/output/project/CAM1事务诊断实板结果-20261026.md)

- [本轮离线成果与接板入口](distortion/output/project/新镜头离线进展-20261025.md)

- [新镜头任务计划](distortion/output/project/推进计划.md)
- [离线工具与运行入口](distortion/output/project/新镜头离线工具说明.md)
- [接板验收单](distortion/output/project/明日接板验收单-20261025.md)
- [冲奖证据矩阵](distortion/output/project/冲奖证据矩阵-20261024.csv)

- [已完成工作与验证范围](distortion/output/project/成果记录.md)
- [实验操作表](distortion/output/project/实验操作表.md)
- [推进计划](distortion/output/project/推进计划.md)
- [原始工程说明和历史记录](distortion/README.md)
- [首次完整交接附件](https://github.com/zhang-yl24/fpga-distortion-correction/releases/tag/handoff-20261010)

源码、必要DDR/PLL IP、真实采集数据、当前实验结果和文档在仓库内。历史构建及封存证据在同版本Release附件中；已生成稳定位流可从`starter-artifacts.zip`导入，无需先重新编译。详见交接说明。

首次交接整理执行文件依赖、SHA256、附件内容和远端上传核对，当时未重新访问开发板；10月25日后的本地构建和实板事件见当前交接点。GitHub Actions不具备PDS许可证和板卡，不能代替整板构建或实物验收。

厂商IP及引用代码保留原有归属和许可，未为整个工程另设开源许可。PDS软件和本机许可证须在各自电脑配置，不随仓库分发。
