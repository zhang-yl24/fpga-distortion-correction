# FPGA 实时图像畸变矫正

> **2026-11-03 新 HDMI 鱼眼提速版已上板：** 1920×1080 矫正唯一新画面实测 **5.0 FPS**，较 C 基线约 4.276 FPS 提升 **16.94%**；HDMI 刷新仍为 30Hz。用户确认“画面正常，比之前流畅，但还是有卡顿”。处理时间约 168.66ms。SRAM 下载、器件 ID/DONE、完整物理与十项时序、位流前独立门检均通过，Flash 未写。见[已上板结果、位流和便携校验](distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/README.md)、[源码与重建](delivery/20261103-hdmi-camera-fisheye-fill8/README.md)、[资源占用](handoff/HDMI_CAMERA_FISHEYE_S3_RESOURCES_20261103.md)、[下一步提帧方案](handoff/HDMI_CAMERA_FISHEYE_PERFORMANCE_NEXT_AFTER_S3_20261103.md)。当前版本仍有卡顿，5 FPS 与 30Hz 刷新分别记录。

> **本分支当前板上版本（2026-11-03）：新 HDMI 摄像头鱼眼矫正 C 版。** SRAM/DONE/器件 ID 已确认，用户确认矫正效果和 KEY1 原图/矫正往返切换正常。矫正实测约 **4.3 FPS**，原图 **30 FPS**，HDMI 扫描 **30Hz**。点击[完整交付](delivery/20261103-hdmi-camera-fisheye-c/README.md)查看已下载位流、源码闭包、标定图与精确参数，以及下载/UART 原始证据。分支 `codex/hdmi-camera1080-fisheye`；下方保留队友独立工程包和各路线历史记录。

## 完整校正帧率优化工程包（2026-11-03）

[进入完整工程目录](delivery/20261103-hdmi1080-board-package/) · [下载 ZIP（约 30 MB）](delivery/20261103-hdmi1080-board-package/hdmi1080-board-delivery.zip?raw=true)

包含完整源码与依赖、三份诊断位流、重建脚本和验收清单。当前为 HDMI 1080p29.97/30 校正配置；组合优化在指定离线模型中减少 12.54% 处理周期，板测帧率与最终时序仍待验收。使用前请阅读目录内说明。


> **已发布候选：新 HDMI 摄像头 1920×1080 @ 60Hz RGB888 直通。** 2026-11-02 SRAM下载/DONE/器件ID通过、Flash未写，用户镜头动作实屏确认“能看到，画面稳定”。输出跟随约148.501MHz输入源，不含DDR/矫正；60Hz是数字信号帧节拍，未独立测量摄像头光学唯一FPS。见[位流、闭合源码、原始回执与portable核验](distortion/results/hdmi-camera1080-direct-display-20261102-a/README.md)。本分支仅封存这次显示验收；后续采图/新镜头标定不在此发布中。下文保留其他路线和历史记录。

## 团队 HDMI 输入路线：1080p30目标（2026-11-01）

**目标：电脑 HDMI 输入 → FPGA 畸变矫正 → HDMI 输出；有效图像 1920×1080、逐行（progressive）、30 fps，显示刷新 30 Hz。** 这是当前开发与验收目标，**不是已经实测达到的性能**。摄像头、新镜头采集或重新标定不是本主线推进的前置条件。

**先读 [1080p30 HDMI 当前计划与交接契约](handoff/HDMI1080P30_CURRENT_20261101.md)、[当前交接点](handoff/CURRENT.md) 和 [环境/历史交接说明](handoff/交接说明.md)。** 外部 RX 并行像素到采集 CDC/DMA、DDR、矫正引擎及扫描/B4 的 RTL 路径已有实现；完整物理 HDMI 输入与 1080p30 实板验收仍未通过，当前保留 UART 候选未获硬件放行。不能用摄像头支线、旧候选、三帧小规模 HDL 或 CI 通过替代本主线证据。

仓库同时保留同学的摄像头 VGA/720p 分工与历史成果，**不将该支线的分辨率、帧率或“暂停 HDMI IN”安排写成全仓主线**。发布版本、未发布本地候选和两条路线的证据边界见上述计划。

## 摄像头分工：720p原图／矫正一键切换（2026-11-02）

当前摄像头板已运行 **OV5640 CAM2 → 1280×720实际镜头矫正／原图切换 → HDMI OUT**。KEY1每按一次切换，默认矫正；LED0亮为矫正请求、灭为原图请求，画面在完整帧边界后生效。KEY0仍复位。新版本SRAM下载DONE确认、Flash未写，下载后30秒UART取得30包/29有效窗口，接受/处理/唯一输出均 **15.0 FPS**，身份不符/拒包为0；不是HDMI30Hz刷新或传感器全部帧。

新版本100项CPU测试、三帧3686400实际显示像素仿真、双角十类内部时序、130引脚电气与2486/2486 CDC case均通过。位流SHA `0ca6d19bf074c73cba0346a22e54ba3afb99a595728e6420a1cbb767b963dfe5`。用户已确认原图／矫正实屏切换正常并授权推送；画面横纹原因仍待对照。没有调整曝光/增益/防频闪、当前镜头参数或插值，没有执行提帧。完整光学迁移验证仍只覆盖左/中区域，UART缺少故障/欠流遥测，数字检查不替代全视场实屏验收。

- [当前切换版位流、下载/UART原件与可离线验哈希证据](distortion/results/camera720-view-toggle-live-20261102-a/README.md)
- [切换实现与验证接续](handoff/CAMERA_720P_VIEW_TOGGLE_20261102.md)、[当前交接](handoff/CURRENT.md)
- [旧统计版回退与两轮15fps证据](distortion/results/camera720-stats-live-20261102-a/README.md)、[提帧后续计划](handoff/CAMERA_720P_PERFORMANCE_PLAN_20261101.md)
- [无UART720p回退包](distortion/results/camera720-calibrated-20261101-a/README.md)、[VGA实屏历史](distortion/results/calibrated-camera-live-20261101-a/README.md)

摄像头任务先做KEY1同场景原图／矫正与振动细横纹对照，再回到PCLK/传感器帧节拍和调度瓶颈。此安排不改变队友独立HDMI输入路线。原始相机照片和大型work构建不进入仓库，SRAM掉电后需重新下载。

下文保留历史阶段，不覆盖顶部项目主线及各支线的证据范围。私人现场相机像素和大型构建中间文件留在本机；封存包提供来源和哈希引用。

盘古676 / PG2L100H-6IFBG676项目。三人轮流推进的私有协作仓库。

**先阅读 [交接说明](handoff/交接说明.md) 和 [当前交接点](handoff/CURRENT.md)。**

## 历史阶段：摄像头接入候选与此前断电

当时的摄像头分工路线是 **OV5640 CAM2摄像头 → DDR/图像处理 → HDMI显示**，其阶段记录曾暂停电脑 HDMI IN / MS7200；该历史安排不适用于顶部当前 HDMI 主线。摄像头仍连接；此前“没有接摄像头”为误点，已更正。

**历史记录：用户当时通知开发板断电，随后已上电并完成新版本实板确认；当前状态见顶部。** 旧processed_output_top测试图曾显示成功，但易失SRAM状态不能描述为当前仍运行。此次仅同步本地文档，不代表Git提交或远端推送。

新camera_vga_output_top目标640×480 RGB565、1080p30居中输出，默认零畸变系数先验证传输。小帧DVP仿真6帧、3,584像素及板层启动/故障控制仿真通过；原生compile/synth/map/pnr/STA完整完成，但**DDR hold/recovery时序未通过**。slow/fast hold最差−0.336/−0.912ns，recovery最差−4.163/−3.156ns，两角setup/removal零失败。尚未生成或下载摄像头位流。

下一步先处理新候选时序并完成引脚/CDC/复位与接口检查，再准备位流→通知上电→验证实时画面→调整当前镜头标定和畸变参数。旧候选的时序修复或测试图实板成功不能直接作为新摄像头验收。

依据：[摄像头接入交接](handoff/CAMERA_VGA_INPUT_20261031.md)、[原生构建摘要](distortion/results/camera-vga-native-20261031-a/summary.json)。目标分辨率/输出刷新不等于已实测相机帧率。新候选无UART接口，不沿用旧COM7/PGHDMI01命令。

## 历史进展

以下记录保留各日期、各候选及各测试环境的事实，不覆盖顶部2026-11-01更正的项目主线。相机图像、HDMI IN诊断、合成测试和RTL回放分别说明来源，历史帧率不作为当前工程的实板验收。

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
