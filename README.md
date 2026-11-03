# FPGA 实时图像畸变矫正

## 当前状态补注（2026-11-03）

**12:04新实板：** [同学stable30源码的我方自编译有界板显](delivery/20261103-hdmi1080-demo-source/progress/20261103-stable30-board/README.md)，bit53f37b7e…，60.003531主机秒1798完整scan/1797不同FrameID/1次repeat，约29.9482个新显示ID/s。这是显示侧统计，处理FPS、输入SOF/DMA丢帧和硬件E2E未测。固定0°/Gamma OFF；本候选厂商异步组实际生效，内部12类0违例仍不等于全局物理签核。



**新的有限三帧/真实路由交付：** [INDEX6连续3帧与60Hz配置最终STA](delivery/20261103-hdmi1080-demo-source/progress/20261103-cont60-route/README.md) 已绑定源码和事件边界。三帧规范化60Hz共享DDR RTL通过；实际route成功但slow setup10213/−2.105ns，无bit、无板验。RCF两网已应用，厂商三异步组未生效，不能把登记当应用。33.941813ms是数字SOF到首扫描观测，旧57044板测23.3613fps及其31ms内部样本仍单独保留。



**10:31后合并交付：** [RX短测/Map、INDEX6单帧引擎与实板固定纯校正计数](delivery/20261103-hdmi1080-demo-source/progress/20261103-morning/README.md) 已分身份列出。冻结57044位流板测468次新完成/20.033 nominal秒=23.36fps；仅两个内部样本31.16/31.26ms，E2E未测。RX新候选仅Map/结构检查；INDEX6单帧16.591656ms不是连续/实板60。新构建与证据都按各项目D盘目录保存。



**09:55请求后最新复核：** main仍为8adda884，但新分支stable30已到[e89a2d42](https://github.com/zhang-yl24/fpga-distortion-correction/commit/e89a2d42c21e6a216df00e4f0fdeb7c94439ba89)（北京时间08:57:53）。它新增三源槽、读写寄存及精确DDR IP约束；回执12类内部时序零违例、最小setup+0.009ns，仍未板测且外部IO/CDC/复位未签核。完整处理模型22.650624ms，不能称60校正fps。见[最新源码/约束与可复用范围](delivery/20261103-hdmi1080-demo-source/LATEST_STABLE30_REVIEW.md)。本轮隔离副本与测试均放D盘指定项目目录。



**当前目标为新购1080p60摄像头经DDR与畸变校正后，输入/输出60Hz、每秒60个新校正帧。GitHub成果包已上传，不代表竞赛已经提交，也未宣布基础/提高任务全项验收完成。**

| 路线/身份 | 已完成 | 仍待完成 |
|---|---|---|
| slowAB保留回退 | 电脑HDMI 1920×1080、29.97Hz，DDR→原图/校正约3秒切换，已实板显示 | 固定纯校正硬件FPS、真实镜头标定画质、全部setup/复位/IO约束、延迟；混合窗口23.21个不同ID/s不等于纯校正FPS |
| 新摄像头60Hz直通 | PR21源同步HDMI显示已现场确认 | 此路径没有DDR/校正，不能替代60个新校正帧/s |
| 同学main新完整工程包 | main@8adda884新增下载与复核入口，源码仍为bdaf8c1；三份30Hz配置诊断bit已生成 | 三版均未板测/时序签核；12.54%仅隔离模型周期减少，both模型22.52ms/44.41fps |
| 原D256处理引擎 | 主集成工程师报告1920×1080连续3帧达到60fps周期预算，RTL通过 | 不是持续实板60；不含实际采集/显示仲裁、物理DDR和路由后时序证明 |
| D256 AREA2/key、HEAD | 各自139项native源码身份和Map资源已核对 | 不继承原D256完整三帧性能结论；key路由预算后未收敛，HEAD仅Map。place-only成功也不是最终route/STA |

详见[新main工程包与D256/key/HEAD身份复核](delivery/20261103-hdmi1080-demo-source/MAIN8ADDA_BOARD_PACKAGE_REVIEW.md)。[同学完整工程包入口固定于main8adda884](https://github.com/zhang-yl24/fpga-distortion-correction/tree/8adda8846f9d3d1f646c5a63d58f128aa786b1cc/delivery/20261103-hdmi1080-board-package)；本独立交付分支没有合并该ZIP、厂商依赖或诊断bit。

下方保留早前快照和同学历史原文；凡历史段落中的“当前目标1080p30”“尚未通过HDMI输入”等措辞，只描述对应日期/候选，不覆盖本补注。新摄像头镜头K/D、同源前后对照、低资源/低延迟与全部时序收敛仍需主工程师继续统一集成验收。

## 今夜离板增量（早前冻结快照，2026-11-03）

**原已上板3秒A/B基线保持不变。** 新DMA5离板父版仍有setup5条/−0.210ns；纯校正PGSTAT02、Gamma、旋转+Gamma完成离板物理流程和诊断bit，setup分别38/−0.314ns、56/−0.379ns、194/−0.894ns，DDR复位/外部IO仍待签核，均未实板验收。资源、精确源码/测试和构建身份见[今夜交付](delivery/20261103-hdmi1080-demo-source/offline-candidates/20261103-night/README.md)。D256独立小系统与原生1080/整机核验仍在推进，不宣布60fps达成。

仓库新`codex/hdmi1080-throughput`分支`bdaf8c1`记录writer/cache隔离模型组合周期减少12.54%，代价为FF/LUT增加；未包含采集/显示仲裁或实板FPS，详见[增量审查](delivery/20261103-hdmi1080-demo-source/NEW_THROUGHPUT_BRANCH_REVIEW.md)。该次审查时main为0408eca0；随后main8adda884仅新增工程包入口，本交付不直接合并吞吐分支。

[测量工具v1源码与34项离线测试](delivery/20261103-hdmi1080-demo-source/measurement/pgstat02-v1/README.md) 已按作者普通原始ZIP的SHA256核验并加入交付，6份RTL语义绑定通过；主线程另报25项合法/反例独立复核通过。仅适用指定纯校正PGSTAT02固定profile，仍不证明现场身份、实际时钟、完整延迟分布或E2E。Library helper元数据失败记录保留，未伪造写回；旧v0不用于验收。

## 团队主线：1080p HDMI 已演示，下一目标 1080p60（2026-11-03）

**已演示：电脑桌面 HDMI 1920×1080、29.97Hz → DDR → 原图/畸变映射 → HDMI OUT，约每 3 秒切换。** 60.066112 秒取得 1798 个扫描签名、1394 个不同输出 ID、404 次重复扫描；不同 ID 约 23.21 个/秒是主机窗口的混合模式统计，不能称固定校正 30fps。桌面输入没有匹配镜头 K/D，尚不能判断校正效果。

**新目标：利用已购买的 1080p60 摄像头演示，并分别达到输入/输出 60Hz、60 个新校正帧/秒，补齐参数与前后画质对照、时序/资源和延迟证据。** 同学刚上传的 [PR #21 / 214cc2ec](https://github.com/zhang-yl24/fpga-distortion-correction/pull/21) 已实屏验证新 HDMI 摄像头1080p60源同步直通，当时main合并为0408eca0，之后8adda884仅增加工程包入口；该直通路径不含DDR/校正，未独立测光学唯一FPS。此前720p/15fps是旧CAM2分工，不能再当作仓库最新结论；设备具体型号、镜头K/D及主校正工程适配仍待核对。

最新源码、时序原件和可复用最小差异见 [1080p60摄像头追加审查](delivery/20261103-hdmi1080-demo-source/LATEST_HDMI_CAMERA_1080P60_REVIEW.md)。初始化TX49条/RX311条与我们的表完全相同，EDID仍首选74.25MHz/1080p30；新直通实际用约148.5MHz输入PCLK转发，不能以此推定校正吞吐或EDID60适配完成。

[本次 HDMI 演示源码交付](delivery/20261103-hdmi1080-demo-source/README.md) 含 50 项项目源码、完整 130 项闭包清单/依赖哈希、可移植构建准备工具、参数对照与同学最新代码审查。它保留已验证回退，与后续实验分开：演示版仍有 slow setup 35 条/−0.579ns，reset/外部 IO 未签核，blanking 为 report-only；固定校正硬件 FPS、内部耗时、端到端延迟、同源画质和全项基础/提高任务仍未验收。当前仅上传源码说明，不包含位流、许可、私人资料或大型缓存。

此前 [1080p30 计划](handoff/HDMI1080P30_CURRENT_20261101.md) 保留为历史阶段与交接契约；[同学摄像头成果](handoff/CAMERA_720P_VIEW_TOGGLE_20261102.md) 和以下摄像头章节完整保留，分别按自己的输入/构建/实测范围解释。主工程师统一集成 RTL，不以支线 CI 或旧 ADF 成绩替代新主线验收。

> **历史原文（2026-11-01时点）：** 以下段落从main8adda884原样保留；其中“当前目标”和“仍未通过”只指当时阶段。今天的60目标与slowAB板显事实见顶部，不能用此旧段落覆盖。

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
