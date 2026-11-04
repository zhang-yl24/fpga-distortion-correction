# PR24合并、G启动阻塞与鱼眼进展交接（2026-11-03下午）

当前目标仍为 **1920×1080，输入60Hz、扫描60Hz、每秒60个新校正帧**；尚未完成持续实板60fps或基础/提高任务全项验收。以下各项按精确源码、参数、位流和计时定义分开，不能拼接最佳数字。数据快照包含15:22:45结束的H Map；后续新运行须另附证据。

## GitHub最新事实与README纠偏

官方API确认 [PR #24](https://github.com/zhang-yl24/fpga-distortion-correction/pull/24) 已合并：2026-11-03T04:54:16Z（北京时间12:54:16），head c53fdecc5dfce176700d8d6160a6ee458e1689d3，merge/main **b3b296979c4bc7c6e2c4ebef1e61879611172e7f**。其双亲为8adda8846f9d3d1f646c5a63d58f128aa786b1cc与c53fdecc；main参考CI41580780980成功。只确认仓库记录，不推断操作者身份。

[main根README](https://github.com/zhang-yl24/fpga-distortion-correction/blob/b3b296979c4bc7c6e2c4ebef1e61879611172e7f/README.md)顶部已写新镜头鱼眼C约4.3FPS/原图30FPS，但后面2026-11-01段仍写“这是当前开发与验收目标”1080p30及“完整物理HDMI输入与1080p30实板验收仍未通过”。这些旧段落不适合作为2026-11-03所有路线的现状。本独立交付更新入口、日期和范围，不改main、不合并PR、不拷贝同学位流/图像/原始UART，保留同学内容及历史记录。分支README也不代表此刻两块板的SRAM仍运行某映像。

## 五条路线的实际完成范围

| 身份 | 已有证据 | 仍不能声称 |
|---|---|---|
| 我方slowAB与57044测量版 | 已板显原图/映射；57044固定profile核心名义窗口23.3613新完成/呈现fps | 未证明新镜头画质、持续60或E2E |
| 同学stable30 e89，我方自编译bit53f37b7e… | 60.003531主机秒、1798scan、1797不同显示ID、1repeat，29.948237新显示ID/s；固定0°/GammaOFF/Penn开发参数 | 不是处理FPS、零输入丢帧、实际新鱼眼校正性能；未测E2E |
| G/Penn SCOUT60 bit74cf25ca… | 原生60时钟模型12类内部检查0；EDID优选148.5MHz、MaxTMDS改为150MHz | 实板未取得ACK/有效处理统计，不能报FPS或启动成功 |
| 同学新镜头鱼眼C bit8c43a77d… | 真实镜头标定、KEY1往返和用户目测确认；处理约4.3FPS、扫描30Hz | 不是60FPS；约222ms是最后一帧内部处理时间，非E2E |
| 新鱼眼tile8/streamscatter16/H | 真实1080整帧engine匹配golden，2076957边沿=16.615656ms；H Map退出0 | 单帧容量60.1842只多51.0107μs；共享采集/扫描、物理DDR、最终STA/bit/板仍未证明 |

此前[stable30我方板测](../20261103-stable30-board/README.md)、[INDEX6连续3帧与失败路由](../20261103-cont60-route/README.md)、[57044固定profile计数](../20261103-morning/README.md)原样保留。stable30显示ID率、PGSTAT02处理计数和鱼眼不同镜头工作负载不能直接计算成处理提速百分比。

## G：内部模型收敛与实板启动阻塞同时成立

G精确bit SHA256 **74cf25cadcd1195131c3bdc3df9ab22c22ccecdc75369dfd4a3b0555a5b696d7**；ADF **453c6178afdf51af8555e09a36ebccc1d182626d8ef05cf82d1ffd3e9a1c2fd4**。139原输入+2约束共141项逐项核验，bit/ADF和独立STA报告哈希匹配。资源FF25610、LUT30444、DRM23、APM68、IO144。

Slow/Fast setup/hold/recovery/removal/MPW/skew共12类零违例；slow setup **+0.012ns**、fast setup+2.589ns。实际厂商异步交互10行、分组负载归属DDR IP，用户60Hz输入/输出时钟与125MHz及其他应保留检查按报告保留；这是匹配IP的模型例外，**不是硅片复位修复或全局物理签核**。外部输入/输出delay仍缺55/111，CDC/物理复位/IO/长期运行仍待验收。也不沿用旧INDEX6路由10213条setup失败或其“异步组未应用”结论到G。

14:41–14:43 G测试一次ARM后采集失败，后续重复同SGA1与规范SGT1诊断raw0/无ACK，无FPS；恢复golden并退出。不能把MaxTMDS75→150MHz修正自动认定为无ACK根因，当前实物输入身份也未独立确认。

15:17–15:19另一个 **启动探针bit e227d7df…** 被动收到32个PGINP004包、2304B、0损坏候选、0PGSIG；32包均cfg/video/DDR PLL锁定、DDR init=true，但RX/TX init=false、input_qualified=false、pipeline_release=false。这定位到初始化/释放前阶段，不证明无PCLK、无DE或EDID/I2C具体故障。其raw计数并非频率计，状态也不保证同帧原子。探针最后恢复golden；不能把其状态包当G已输出60校正帧。

## 同学鱼眼C：可复用标定与真实效果，吞吐仍是约4.3FPS

PR24的[完整交付](https://github.com/zhang-yl24/fpga-distortion-correction/blob/b3b296979c4bc7c6e2c4ebef1e61879611172e7f/delivery/20261103-hdmi-camera-fisheye-c/README.md)、[参数与35图数据集说明](https://github.com/zhang-yl24/fpga-distortion-correction/blob/b3b296979c4bc7c6e2c4ebef1e61879611172e7f/delivery/20261103-hdmi-camera-fisheye-c/calibration/README.md)、[实板证据说明](https://github.com/zhang-yl24/fpga-distortion-correction/blob/b3b296979c4bc7c6e2c4ebef1e61879611172e7f/distortion/results/hdmi-camera-fisheye-live-20261103-a/README.md)固定到上述main。用户确认效果和KEY1往返，仍报告迟滞卡顿。正式C bit为8c43a77d9ddce72dc7015ef7f63aabe37ab6758dd698e2e811b669c5aa5ba047，ADF7b21d061…，PGHFPS02 BuildID11030001/ProfileID ed59f83e3cfbc77b。

| 窗口 | 样本/名义秒 | 新处理FPS | 新呈现ID/s | 扫描Hz | 最后一帧内部ms |
|---|---:|---:|---:|---:|---:|
| 矫正 | 30/29 | 125/29=4.310345 | 124/29=4.275862 | 30 | 222.479248 |
| 原图 | 30/29 | 870/29=30 | 30 | 30 | 31.371616 |
| 切回矫正 | 12/11 | 47/11=4.272727 | 4.272727 | 30 | 222.259016 |

来自远端原回执名义125MHz计数；主机到包交叉核对不是校准时钟。数字源帧计数60Hz不等于光学曝光唯一FPS。原始cache_hits回绕修正见同学VERIFY_README，未据旧首尾差计算新的cache结论。本次交付工程师只读JSON/说明，没有下载图片/bit/wire、重新跑其完整release验证或操作同学板。

实际镜头采用OpenCV **fisheye四项D**，不是旧Penn Brown系数：K_source与K_output分开，balance0.5/R=I；精确数值见STATUS.json及同学参数文件。35有效姿态分28训练/7留出，留出均值0.391519、最大0.870875原生像素；定点全网格最大约0.006365像素是映射数值误差，不能代替全视场光学验收。优先复用这份已绑定镜头的profile/ROM、完整identity原图和同源参数说明，保持算法、投影、定点位宽与测试oracle一致，不能直接套入未核身份的Brown主线。

## 我方鱼眼tile8：完成整帧RTL，物理仍在Map阶段

CACHE_PROFILE2→3，在同一固定源与AR/R/AW/W背压下，真实8×8扫描→0°旋转→鱼眼mapper/ROM→D256 INDEX6/Q256→双线性→GammaOFF→双tile writer→实际写仲裁→行为DDR。2,073,600像素逐一对golden、CRC均d3be1a4d；50778次miss与独立模型精确一致。边沿定义是engine begin_frame接受上升沿→done上升沿、post-NBA观测，不加1，不从源帧描述符接受开始。

Profile2为2926369边沿/23.410952ms；Profile3为2076957/16.615656ms，降低29.0261%。这是隔离engine单帧收益，不能与同学实板222ms直接拼接为板上倍数，也不能借用旧Brown连续3帧证明新鱼眼连续60。行为源预装，未包含真实采集/扫描并发；仅51μs预算余量，必须继续核仲裁和物理效率。

另有17项官方项目RTL的XSim短例通过（背压、fault、reset、writer、cache和joint crop），含测试适配修改并保留失败记录；这不是厂商受保护硬DDR模型验收。同版本HMIC1.10文档允许AWLEN0单UI beat，但现有XSim不能解密Mentor/Synopsys封装，AWLEN0/1/7/15驱动读回尚未完成。需要兼容已有授权仿真器或厂商相容模型，不能以文档合法替代硬控制器效率。

H按已测整帧profile独立集成，146项源码逐项哈希通过；15:22:45 Map退出0，状态MAP_EXIT0_STRUCTURE_AUDIT_PENDING。未发布Map资源或最终PNR/STA/bit/板结论；不得继承G/Penn的+0.012ns。F早前仅顶层接线的候选也不作为H功能验证。

## 接续验收

先把G的RX/TX初始化与release原因核清，再证明实物输入身份/60信号、共享DDR下持续新校正帧和扫描；鱼眼H须完成结构/资源/双角最终STA与独立位流身份。继续补同源raw/corrected、实际镜头全视场画质、动态旋转/Gamma、内部延迟分布与外部光学E2E、热/长期稳定、资源和正式基础/提高任务清单。GitHub源码说明交付不等于竞赛提交或全项通过。

STATUS.json为去标识派生摘要及来源哈希；原件保持不改，机器路径、私人图像、rawUART、bit、ADF和厂商受限原件不随本次上传。所有新整理在D项目工作空间。此次只有文档/摘要，未执行新硬件、EDA或HDL。
