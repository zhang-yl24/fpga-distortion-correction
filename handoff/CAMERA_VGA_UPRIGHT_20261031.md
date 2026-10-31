# 2026-10-31 相机画面 180° 倒置修复：实板确认通过

> 仓库内可移植成果：[已验证位流、下载回执及实板反馈](../distortion/results/camera-vga-upright-live-20261031-a/README.md)。下文work绝对路径为本机历史证据，不要求克隆者具备原7.7GB中间目录。

> 最新任务顺序（2026-10-31）：先推送当前成果，然后在现有640×480模式完成实际镜头畸变矫正及验收，之后再讨论清晰度和帧率。见[当前矫正任务](CAMERA_VGA_CALIBRATION_NEXT_20261031.md)。

本交接截面为2026-10-31最新用户实板反馈：新upright位流已生成、验证并下载至易失SRAM。`bit-fast-20261031-b` 已取得 `Verified=true`，`program-fast-20261031-a` 已取得 `Passed=true`、`DoneConfirmed=true`、`FlashWritten=false`、`CleanupErrors=[]`。用户确认“已正立、左右正确，画面持续更新”以及“LED5/6 闪烁，LED7 一直灭”。方向修复与基础实时链路通过实板观察，证据为[用户反馈](../distortion/work/camera-vga-upright/live-observation-20261031-a.json)，SHA256 4ca6a4587f586032e06915e7da312fb77b4da3857116ea3b39d525da0204cbd6。当前640×480；用户最新指定先在当前640×480模式完成实际镜头畸变矫正，清晰度和帧率讨论后置。

用户此前确认原 camera_vga_output_top 实时画面更新、LED5/6闪烁、LED7长灭，但画面180°倒置。旧工作位流 acec0a6528760cabe8291d4452c635e26d7e0f7b3fdfef997a386d1c365b25e0 与原输入/证据全部保留。下方16:33–16:46各节属于过程快照，不覆盖本次最新审计结论。

## 位流、SRAM下载与新实屏确认已完成

新位流为 `work/camera-vga-upright/bit-fast-20261031-b/generate_bitstream/camera_vga_upright_top.sbit`，SHA256 `e3c889f29c6fb74dda71fc49b5b6bcf2b53e9055720c18ae7238997bbe6ca1ae`，3,791,112字节，原生header时间17:14:13、Design为camera_vga_upright_top、Device为Logos2-PG2L100H--6-FBG676。它绑定最终ADF `0baea59b…392b5`。该阶段重新执行STA、CPU gate、位流生成；十表通过、时钟/摘要身份和全部例外路径保持，完整位流头与实际阶段顺序验证通过。[verification.json](../distortion/work/camera-vga-upright/bit-fast-20261031-b/verification.json) SHA256 `f8ad8c474c2084595fa8214b21af58c2f9b7b175e0a29e6155a86933d0804a00`。

主任务已在北京时间17:16:00–17:17:02完成易失SRAM下载。实际 [program-fast-20261031-a/receipt.json](../distortion/work/camera-vga-upright/program-fast-20261031-a/receipt.json) 为 `Passed=true`、`DoneConfirmed=true`、`FlashWritten=false`、`CleanupErrors=[]`；计划SHA256 `a1414cb872648051d4fb89f334f20010acbc496fe8f468b4ab279af6411f8195`，位流仍为上述e3c889…ca1ae。记录的自有PID为34560、23052、32300、33976，下载前已通知用户并复用本会话已确认上电状态；未写Flash。新的[轻量证据索引b](../distortion/work/camera-vga-upright/evidence-index-20261031-b.json)追加真实生成与下载回执，旧索引a保持不变。用户已确认新方向、实时画面和LED5/6/7正常，不无因重新生成/下载；新upright帧率仍未测。最新[轻量证据索引c](../distortion/work/camera-vga-upright/evidence-index-20261031-c.json)追加此次观察，旧索引a/b保留各自快照。

## 接续必须使用已审计的fast路径

原 `camera_vga_upright_bitstream.py` 的完整prepare已真实结束：owned session70541、exit0、Prepared=true。它执行了完整语义审计并产生原 `bit-20261031-a/bitstream-plan.json`。后续通过 [authority-seed-20261031-a.json](../distortion/work/camera-vga-upright/authority-seed-20261031-a.json) 绑定真实完成记录，seed SHA256 `c77c1014ae4d586e575bc6576109d08cf8e2681ad1e5e228e9234f98bba6d973`。不得仅凭四个准备文件已存在就伪称原prepare完成。

新 `tools/camera_vga_upright_fast_bitstream.py`（SHA256 `c053b4b32357eec40d733abe837020620733e40ca8f52a47b13c5de808903a5c`）复用已经通过的功能图/路由/复位语义证明，每次仍重核完整479项原authority输入、35项工具/执行文件、原四个准备产物、seed、完成记录及新计划/工具。新鲜STA十表与例外比较、实际ADF、位流头、唯一gen_bit_stream命令、执行阶段、超时和仅清理自有进程全部保留；没有把原生exit0当作验证通过。fast-program消费该fast验证及完整哈希闭包。不要重新走旧bit/program的重复full-authority流程：最少13次authority，每次又重复多轮原始proof/graph/route解析，按本轮首轮约258秒会耗时约56分钟；这不是新的设计检查需求。

**所有fast工具的prepare/execute/verify以及编程计划参数必须传规范绝对路径。** 首次 `bit-fast-20261031-a` 的原生STA、gate与gen_bit_stream均完成、exit0，但execute保留CLI相对work，四个watched文件key仍相对，严格 `inspect.drift` 因 `p != p.resolve()` 拒绝验证；verify中gen输入命令比较也需要绝对work。不能改失败receipt或冻结工具来掩盖；原a完整保留，[bit-path-retry-20261031-a.json](../distortion/work/camera-vga-upright/bit-path-retry-20261031-a.json) 记录原因。主任务以绝对路径重新prepare/execute全新b目录，重新原生生成并验证通过。后续接续使用b及其真实哈希，不使用a的未验收位流，也不再无因重跑b。

30项CPU检查通过，证据 [fast-bit-helper-tests-20261031-a.json](../distortion/work/camera-vga-upright/fast-bit-helper-tests-20261031-a.json) SHA256 `22ec3bce1b6b9a48cf9c87b49a36f98502268e3d161e5fd45562e83fc20d71ad`；独立review确认seed完整闭包、原生gate与阶段约束，没有修改原冻结helper。

## 最新完成：正式效果与最终IO/CDC补证

最终ADF为 `0baea59b6633ef93278c74c00602cb2cad688d96c796458cf54243a7ab6392b5`，源ADF为 `207b840c5e024f600f555e1607ac39944e330439e9716f93fef2a80284c0967b`。正式 [reset-effect-20261031-a.json](../distortion/work/camera-vga-upright/reset-effect-20261031-a.json) 已通过，SHA256 `873871748f4fffa73aededdb3140bbb64287fff2d2f706e66b4f3b6ea6006e12`。436项输入及25项工具哈希重核；36,499个功能单元、17,417个FF的参数/连接/位置完全一致。33,722条路由仅 `_N127` 改变，其余NETANNOTATE和非约束非路由语义相同，明确 `RoutingUnchanged=false`、`OnlyRequestedRoutingChanges=true`。

十张内部时序表全部0失败：slow setup/hold/recovery/removal/mpw为0.090/0.135/2.965/0.313/0.035ns；fast为2.770/0.017/4.771/0.159/0.035ns。数据setup/hold false path均0；每角recovery/removal精确对应本候选245条逻辑检查、490个原生变体，16个非false-path例外分区的语义多重集合相同。审计一次通过，未放宽真实时序标准或借用旧候选例外。

最终 [io-cdc-native-proof.json](../distortion/work/camera-vga-upright/io-cdc-native-final-20261031-a/io-cdc-native-proof.json) 的结构与原生补证均通过，SHA256 `e6128eb6b6de5c8e5180cb76ec32e3105afe153c2e0c637ca23ffe577b34afba`。35个精确级间连接覆盖双角setup/hold共140项，最小setup 6.086ns、最小hold 0.171ns；34位Gray覆盖68个角案例，最大到达时间0.958ns；最终128个原生site映射全部匹配（含71个DDR memory脚、2个DDR参考时钟脚、14个CAM2脚）。

这些是限定内部数字时序、同步结构/逐路径和引脚site证据；模拟MTBF、所有CDC的普遍证明、实测外部AC和原生电气设置仍未签核，`TimingAccepted=false`、`HardwareReleaseAllowed=false` 不因本文而提升。功能库中的DRIVE/SLEW参数不能代替实际pad电气证据。后续诊断位流与SRAM下载须走各自新计划/回执，不写Flash、不恢复HDMI IN支线。

离板证据入口 [evidence-index-20261031-a.json](../distortion/work/camera-vga-upright/evidence-index-20261031-a.json) 保留16:55快照，后续已完成的位流与下载记录见新索引b；大报告、ADF和厂商网表不复制。新候选实屏方向、更新和LED观察已经补齐；新FPS仍待测量。

## 本轮改动

新入口 board/camera_vga_upright_top.v，仅替换顶层模块名和相机初始化实例；新初始化 rtl/experimental/ov5640_cadence_upright_init.v 复用冻结命令表，在固定两个地址采用幂等目标：3820由06改00、3821由00改06。相对旧设置同时反转上下和左右方向，不能误改成06/06。

依据本地OV5640 v2.01数据手册印刷4-1/7-12页及锁定ST官方驱动 vendor/reference/st-ov5640/ov5640.c 的 OV5640_MirrorFlipConfig：3820的bit2/bit1为ISP/sensor vflip，3821的bit2/bit1为ISP/sensor mirror；其他位保持。ST来源commit为52c727ac10a427fe7a400d3a4783adc814ee075e，源码SHA256 f13efaeb4e51343e443d4c19965bb47826cec6b32ada980dff9c84f1f918a121。

两个方向寄存器写后立即精确读回，即使CHECK_WRITES=0也不能绕过；最后启动写之前和之后的验证清单由7项扩成9项。原表第245项已有一次3008=02，因此不声称前检查发生在所有首次唤醒之前。命令数仍为264，其余262个写值、地址及delay均不变；分辨率、裁剪、字节顺序、VS/HREF极性、PLL/PCLK、DDR和处理几何不变。

独立源码审查通过，证据为 work/camera-vga-upright/orientation-evidence-20261031-a.json（SHA256 40a8e4a4c5b55e49c1301380f44fe29c309d0822c69f56303589d2d16aa8cc66）。数字SCCB仿真 sim-20261031-b 已通过11场景、1,770笔事务及49,539个TX位周期，真实reg16_i2c quarter=68；7项独立oracle CPU测试通过，无源码漂移。仿真报告SHA256 23370b50fcfbf7295e644d0e61df335ea921353d3923fa947940d744996aa900。首轮a因testbench watchdog常量溢出失败，保留失败记录；修正未改RTL。

仿真证明默认264次写中仅方向两值变化、CHECK_WRITES关闭时仍强制方向读回，以及即时错值/最后启动前错值/启动后瞬态恢复/持续错误拒放ready。原FSM未同时执行，等价范围为独立冻结表所生成的线级写序列，不声称完整FSM周期等价或实物方向已正立。

新构建工具24项定向CPU测试通过。独立pds-20261031-a已完成综合、布局布线和STA（828.067秒，原生exit=0、输入无漂移）；新plan SHA256 5c598b3155f5d1ec5295fbdf81896598b0bf912e501e201230e343553685db9e，108项源码、109项编译输入、121项输入哈希。当时尚无新位流，后续自身时序修复、位流生成和验证已在顶部登记；未继承旧候选网名和绕行修复。

## 分辨率与帧率

当前有效相机内容为640×480，HDMI扫描刷新为1920×1080、30Hz。用户已对旧 `acec0a65…b25e0` 位流的LED6人工计时：10完整周期约13–14秒，`processed_frames[4]` 每周期32帧，估算处理完成率22.86–24.62fps，报告约23–25fps（约24fps）。这不等于输入传感器或显示独特新帧率实测，不能写成HDMI 30Hz即30fps，也不能归到尚未完成实物测量的新upright候选。旧合成源约10.91fps属于另一位流，不适用于当前相机。

后续1080p采集仍是升级目标，已核帧缓存/主要静态参数可容纳；传感器模式、DVP时钟和持续吞吐尚待验证，不能承诺1080p30。顺序为先修方向，再验证目标分辨率和帧率，最后按选定传感器模式完成镜头标定。

开发板最近仍为用户确认上电状态。需要新下载时先告知用户；若用户途中断电，必须取得新的上电确认。HDMI IN/MS7200支线继续暂停，没有UART访问、Flash写入或远端推送。

## 16:33 原生检查进展

新原始ADF为207b840c5e024f600f555e1607ac39944e330439e9716f93fef2a80284c0967b。原生退出0不等于时序通过：slow/fast各有一条DDR数据hold失败（-0.018/-0.248ns），实际端点rddata_r1[43]、末端网络_N127，精确setup余量5.052/5.910ns。正在仅对这一数据分支准备物理绕行，不能通过falsepath隐藏数据hold。其余setup/removal/mpw已非负。复位恢复检查另外需要基于新网表和供应商结构重新证明精确范围；新report实际每角245逻辑检查、127源端点对，不能直接继承旧审批。export-a已完成，baseline-query-a正在只读导出实际路由和匹配复位对象。尚未生成或下载修正版。

## 16:43 单线修复已保存，等待最终检查

新reset-proof-a已pass（SHA dc211a789cca0d34eedf3f63e0d1a1f59375661b37e450861b40f88809cf83e5），只证明精确范围和当前原生图，不单独批准时序。physical-route-reset-a已clean完成86.208秒，实际只请求_N127经ZDNE[0]:SRB_336_774>IDNE[0]:SRB_342_780绕行，并应用5组精确复位约束。保存ADF为0baea59b6633ef93278c74c00602cb2cad688d96c796458cf54243a7ab6392b5。final-export-a正在新进程重新STA与导出网表；尚不可声称hold消除、完整时序通过或硬件可下载。

## 16:46 修复后完整内部时序通过

final-export-a已clean完成122.307秒，无输入漂移/diagnostic，保存数据库仍为0baea59b…392b5。新进程十张表全部0失败：slow setup/hold/recovery/removal/mpw为0.090/0.135/2.965/0.313/0.035ns，fast为2.770/0.017/4.771/0.159/0.035ns。快速物理范围核验33722条NETANNOTATE仅_N127改变，指定连续绕行存在、其余路由和非约束非路由语义完全相同（quick证据SHA68a1b7bd…689d4）。正式reset effect/最终网表比对与final IO/CDC逐路径补证仍在进行；尚无新位流或下载，实际FPS仍未知。

## 下载前旧位流人工计时：处理帧率约23–25 fps

在新upright下载前，用户测旧camera_vga_output_top的LED6从第1次亮起至第11次亮起（10完整周期）约13–14秒；LED6接processed_frames[4]，每完整周期32帧，因此320/14至320/13 = 22.86–24.62 fps，报告约23–25 fps（约24 fps）。这是旧acec0a65…b25e0在640×480下的处理完成计数人工估算，不是输入传感器实测帧率，也不是HDMI独立新帧呈现计数；HDMI仍30Hz刷新。新upright已下载但未重测帧率，不能把旧测量归到新候选。证据：work/camera-vga-upright/frame-rate-observation-20261031-a.json。
