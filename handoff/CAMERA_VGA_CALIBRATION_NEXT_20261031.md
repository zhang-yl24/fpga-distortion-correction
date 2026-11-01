> 2026-11-01最新实板结果：本次实际镜头矫正位流已下载，用户确认画面持续更新、直线明显变直，LED5/6闪烁、LED7常灭。首次实屏观察通过；仍为640×480有效相机图像，后续再评估帧率/1080p。见[矫正构建与实屏交接](CAMERA_VGA_CALIBRATED_BUILD_20261101.md)。下方为标定/构建阶段历史。

# 当前主任务：先完成实际镜头畸变矫正

> 2026-11-01更新：12训练/6验证采集完毕，K/D数值验证和f240定点映射通过；下一步为独立矫正VGA候选RTL/时序及实屏验收。详见[最新标定交接](CAMERA_CALIBRATION_PROFILE_20261101.md)。下文采集待办为历史记录。

2026-10-31用户明确顺序：先推送当前成果，然后先实现畸变矫正，再讨论清晰度和帧率。该指令覆盖此前“先评估1080p模式再标定”的顺序。

当前保留已确认的camera_vga_upright_top基线：640×480 RGB565，HDMI以1080p30扫描，画面正立、左右正确、持续更新，LED5/6闪烁、LED7灭。位流SHA256 e3c889f29c6fb74dda71fc49b5b6bcf2b53e9055720c18ae7238997bbe6ca1ae。当前畸变系数为0，不能将本次方向修复称为实际镜头畸变已矫正。

## 执行顺序

1. 保持当前640×480传感器模式、裁剪、方向和焦距；确认当前镜头及实物棋盘内角点/尺寸。既有9×6、20mm是旧模板，不能自动沿用。
2. 准备同模式、同方向的独立原图采集候选，复用既有PGFRAME1/RGB565采集工具。当前upright显示顶层没有UART原图导出，旧采集顶层仍调用旧方向初始化，不能直接视为等效。
3. 采集当前镜头多姿态棋盘原图。已有fisheye标定工具要求至少12个不同训练姿态和3个独立留出姿态；旧10月6日标定和10月25日两张自然场景不能替代本轮数据。
4. 求真实K/D，检查模型对目标视场的适用性，审计定点和边缘映射误差，再生成独立calibrated VGA候选。软件参考与RTL逐像素核对、时序/资源检查后，上板验收直线、边缘、黑边及运动画面。
5. 当前镜头校正验收完成后，再讨论1080p和帧率优化。当前任务不因处理率约24fps或显示1080p扫描而转回HDMI输入排查。

上板前先通知用户；若用户断电，取得新的上电确认。已有正确显示位流保留作为回退基线。暂不重新测量帧率，不做分辨率升级，不改冻结的已验收来源或回执。

## 本轮用户已确认的实物条件

用户接手项目后没有更换过当前镜头，不知道队友此前是否更换。以现在连接的镜头为唯一标定对象，重新采集，不推定它与任何旧档案相同。实物棋盘为7×10方格，即6×9内角点（旋转摆放可等价记9×6），每格25mm。内角点是棋盘内部四个黑白格交汇处，不包含外轮廓。采集前固定当前对焦/焦距与传感器模式，棋盘保持平整。

## 推送后离板准备

当前实板成果已推送origin/codex/camera-vga-upright，提交0643c1856175a3963d01a3d47f07ad121776fda8（远端读回相同）。之后开始的采图准备尚属本地下一阶段：新增board/raw_camera_capture_cam2_upright.v及-sources.json，以旧raw_camera_capture_cam2_ref为采集基线，仅替换顶层名和初始化实例为当前ov5640_cadence_upright_init；96项依赖文件存在且哈希已绑定。旧PGFRAME1、CAM2、640×480、UART921600保留，参考FDC仍需新候选审核，尚未运行综合/布局布线/位流或下载。不能把显示版本的时序通过继承到采图候选。标定会话位于work/camera-vga-calibration-20261031，真实棋盘图与K/D仍未产生。


## 远端分支检查与独立采图诊断

2026-10-31已确认当前成果通过PR #15合入origin/main（71d4677），与0643c18内容相同。其余四个delivery分支属于独立离线候选/证据归档，当前采图和镜头标定不依赖它们，未执行合并；详见[分支检查](BRANCH_REVIEW_20261031.md)。

新增tools/prepare_raw_camera_upright.py与run_raw_camera_upright_diagnostic.py：96项来源、17项显式设计、DDR IDF内部74项展开，4处include仅在暂存副本改写；新FDC去掉显示版reset_n/C22，加入UART TX/C24，128引脚逐项匹配旧CAM2采图映射，并给camera_pclk与pixel_clk双向增加8ns/min0诊断边界，不沿用旧broad clock groups/false paths。8项准备器/执行器正反测试通过。Windows路径长度需使用短运行目录，过长路径会在写入前拒绝。

首轮独立原生离板诊断位于work/raw-camera-upright/d1，计划SHA256 951b33ee22e4c6a3910414ff1eaaccfd15a8925dc97462ae6c31a31e4f3ab8f0。本段写入时已启动compile/synthesis/route/STA，最终结果须读取该目录execution-result.json，不能把启动或exit0当作时序通过；不生成位流、不下载。新来源不能使用显示版本fast-bit/fast-program的旧seed放行。

采图顶层HDMI预览为720p60扫描，源图预览每4行/列采样到160×120后放大；UART导出的PGFRAME1仍为完整640×480 RGB565原图。下载后预览清晰度降低不代表标定原图降为160×120，不能用屏幕照片代替UART原图。

## 首轮采图原生诊断完成：尚未达到上板条件

北京时间2026-10-31 22:04:00–22:11:20，d1完整执行compile/synth/map/place/route/route-optimize/STA，440.829秒，exit0、来源无漂移、原生错误0，STA前后最终ADF一致（SHA256 `15b1750939e309b7f2c7f278cffb81fd993b02fc746de2c73e55de20b3cd1f62`）。128项实际封装引脚全部与CAM2原图参考一致。**构建完成不代表时序通过；本候选未生成位流、未下载，板上仍保留此前已验收的显示版本（除非用户后续断电）。**

时序摘要：slow/fast setup最差+1.106/+3.617ns、均0失败；hold最差−1.527/−1.024ns、分别6/8个失败端点；recovery最差−4.031/−3.007ns、分别245/237个失败端点；removal最差+0.311/+0.157ns、均0失败。

已定位保持时间问题：摄像头输入cam_data[1/2/5]到preview及raw capture接收寄存器共6个端点，两角均失败；它们使用暂定input min0预算，须复核真实接口预算或修复采样/路径，不能掩盖，也不能据此宣称已测得物理故障。另有DDR读回路径rddata_r1[0]和rddata_r1[32]在fast角分别−0.193/−0.133ns。恢复时间问题集中在当前网表的DDR复位域，必须重新证明精确端点与约束，不能复制显示版的旧网名或直接套旧豁免。

详细检查见本机 `work/raw-camera-upright/d1/native-review.json`，SHA256 `fdb086b175a928805cc5afd1d40ef413ed32dd5e9d7676583e8eea48eaea1826`，含全部513条负裕量路径摘录、十类summary原始行及真实引脚核对；完整原生报告保留在d1。它是本地诊断证据，不是可下载成果。

本轮共53项CPU检查通过：新增准备器/执行器8项，已有原图接收、标定与IDF来源45项。旧默认build临时目录导致第一轮45项回归在源清单测试处停滞；已核验并终止该自有测试PID，改设FPGA_TEST_WORKDIR到work/raw-camera-upright/cpu-tests后完整45项2.07秒通过。后续测试继续显式使用可写临时目录，勿再卡在旧build测试目录。

下一步先在该采图候选自身来源上处理摄像头采样裕量、两条DDR保持路径和复位范围，完成新候选CDC/IO审查再生成位流；然后通知用户上板采棋盘。当前镜头数据/K/D仍无，未恢复1080p或帧率优化，未合并远端delivery分支。

最新硬件安排：用户已明确确认开发板断电，继续离板修复。需要硬件时通知用户并取得新的上电确认。不得沿用此前上电状态或默认SRAM位流仍在运行，电脑上的已验收位流保留作为恢复基线。

## 注册启动复位候选 d2：复位证明通过，保持时间仍待修复

原采图顶层的 `&power_count` 组合译码直接作为复位释放源，不能套用显示版的外部复位证明。新增独立 `raw_camera_power_ready` 与 `raw_camera_capture_cam2_reset`，在第1,048,576个27MHz上升沿注册置位并保持；未改d1来源。s1实际20位全周期仿真及3位边界共2,097,216项检查通过，97项来源/18项显式设计的新d2完整原生构建468.99秒完成。最终ADF SHA256 `df4d54bb3c67ab0374dd47720160e1fee70bc82b424c6649b8d47a47e852dabf`。

d2双角setup +0.914/+3.599ns，0失败；hold −1.381/−0.983ns，各5个失败；recovery −4.053/−3.056ns，245/227个失败；removal +0.235/+0.102ns，0失败。当前失败分支为cam_data[1]的preview first_byte[1]、cam_data[2]的preview first_byte[2]和pixel[10]、cam_data[5]的raw capture first_byte[5]，以及DDR group1 rddata_r1[8]。h2绑定逐条同端点setup余量，不能用整个时钟对的最好/最差值代替。

当前有效只读导出为e3，原生查询和完整路线为q3（query body文件名仍为q2-body.tcl）；e2因后续修正Windows dummy.v换行，工具字节绑定已过期，q2在启动PDS前拒绝，均保留不可覆盖。p3/proof.json已通过原生名称、17,889原语连接、启动sticky寄存器、打包INV/LUT固定输入后的真实复位依赖及原厂IDF/74内部文件逐字节核对：内部126对加入口1对，共127对精确复位范围，TimingExceptionApproved/HardwareReleaseAllowed仍为false，尚未应用。

完整q3路线解析通过：16,841个net route、285,368个物理节点；能区分nt_cam_data[2]四个分支，后续只允许改变5个已测失败分支，其他共享分支须保持一致。复位/多分支解析24项CPU检查通过。下一步由实际未占用节点和原厂wire规则选择分支绕点，对d2副本应用限定修改；新进程重新运行完整STA，检查约束增量、功能/布局以及全部其他路线不变。距离不是延时证明，执行保存也不是时序通过。

输入PCLK/延时仍是当前诊断预算，不能增大input-min、改采样沿或豁免数据路径来消除失败。当前没有新的采图位流、棋盘原图、K/D或硬件下载；开发板保持断电，摄像头与HDMI OUT主线不变，HDMI IN继续暂停。

首轮局部分支修改a2在2026-10-31 23:07:02–23:07:55运行，52.871秒、native exit1：`_N57`绕线命令成功，第二条`nt_cam_data[2] → M3:CLMA_243_420`的channel1绕点被原生manual_route拒绝。尚未到复位约束和save阶段，没有有效派生ADF/位流。a2失败日志与回执保留；回执Error为后续读取未执行的复位查询失败，真正原因见stdout.log末尾`E: Manual Route failed.`。工具后续已修正为即使提前中止也保留native Diagnostics。新a3从原d2重新准备，仅调整该失败分支到channel0的`SRB_216_564 → SRB_222_570`，不得以a2失败副本作输入。

新增effect审计器独立适配raw：验证CDB只增精确复位约束、共享net其他分支不变、每个请求绕点实际在路径内、功能/FF布局一致、双角检查数量与逐路径延时变化边界。16项测试通过，另6项waypoint证据正反测试通过；这些是工具验证，不等于派生候选已通过。新工具/文档仍仅保存在本地，尚未提交或推送。

### a3失败及无保存的路由对照

a3使用另一个channel0绕点仍在同一nt_cam_data[2]分支失败（59.479秒、exit1）；未达到save或复位应用。之后probe1在独立d2副本上拆同一M3分支，紧接的show证明叶子确已消失，其他叶子仍在；用原有ZDSE1→IDSE1连续段恢复时原生报Unknown error，catch记录恢复返回1。probe2对同网另一条独立M0:CLMA_249_516分支拆线并按原有ZDE1→IDE1恢复，同样Manual Route failed。两次源ADF及本地input.adf均无字节漂移，退出，无save/位流/硬件访问。尚不能区分直接IOL源的工具限制和其他路由状态问题，不能断言芯片共享分支物理上不可修改。

probe3尝试原厂manual_route -file通路恢复；直接采用show输出树的格式被工具误读，报末端pin不能作为driver，不能作为硬件可达性证据，也未保存设计。全部失败记录保留，后续不要把show树直接当作Report Net To Status文件格式。下一项复核原厂物理输入延迟配置或其他有证据的修复方式；外部STA input min0/max5预算不变，不能以调整约束假装修复。

### 当前d2的限定IO/CDC数字核查

新增audit_raw_camera_io_cdc.py，8项测试通过；真实e3检查输出io2/io-cdc.json。20位Gray、10条标量链、6条复位释放链结构通过且均同BLE；34位保持数据的冻结/接收使能和预览请求确认核对通过。原生双角各60条max-delay路径通过，最大到达时间slow 1.595ns、fast 0.999ns，Gray及held路径无缺失。128脚/71个DDR脚/UART C24/CAM2 D5 AA23映射匹配。

io2仍明确ScopedDigitalChecksPassed=false：缺最终派生候选effect回执和最终原生IO site查询。io2/query-body.tcl提供后者精确查询。该记录只属于d2/e3，不继承到未来修改后的候选；外部AC、电气设置、模拟MTBF和实板表现未签核。用户板卡保持断电。

## 独立物理输入延迟候选 d3

原厂Logos2 GTP指南及安装库确认PG2L100H支持GTP_ZEROHOLDDELAY，设置为NODELAY或100ps至1500ps、100ps一档。PAP_IO_IN_DELAY整数与实际延迟/Gray码关系尚未查明，未猜值使用。新raw_camera_capture_cam2_delay顶层通过raw_camera_input_delay给8位cam_data统一显式加入GTP_INBUF(LVCMOS33/TERM_DDR=ON)→GTP_ZEROHOLDDELAY(1500ps)；原图采集和预览均接新输出，其余逻辑保持d2父版。使用同一posedge、同一传感器模式/方向、同一输入min0/max5及跨域约束；FDC与d2逐字节相同。

98项来源、19项显式设计、128脚、父源码/清单和原厂技术原语库已绑定，8项准备器测试通过。s2使用本机真实GTP_INBUF/GTP_ZEROHOLDDELAY仿真模型，256种字节/768项检查通过，覆盖1500ps前后输出边界，12.68秒无漂移。该结果只是原厂功能模型的名义延迟，不证明PVT/实际IO配置或STA通过。

d3/plan.json SHA256 `1ac68243d99c229f34a78e41cb58bdb92ed9a7a52ea80f15c6b1a5fcb543d4d5`。原生构建已启动，限时1800秒；后续读取execution-result.json及新报告。必须验证8个延迟单元的真实映射和全部数据消费者双角裕量，重新证明本候选复位、IO/CDC，不能套用d2的p3/io2、旧物理网名或显示版位流seed。所有旧候选、失败回执和来源均保留。开发板继续断电，没有位流生成或下载。

### d3完成：摄像头hold消除，剩余单条DDR路径

d3完整构建469.352秒，exit0、来源无漂移、STA前后ADF一致，最终SHA256 `ed79659474133550c43982e6f9fe567007c972b39b398cdbaa6c5d4d7224495f`。8个ZHOLD均有原厂map日志成功打包至对应IOL；e4真实功能网表也逐个保留V_IBUF→V_ZEROHOLDDELAY(1500ps)→capture_data。e4只读导出86.116秒通过，无漂移，17,937原语、6,963FF。

双角setup最差+1.311/+3.645ns，均0失败。slow hold +0.059ns、0失败；fast hold −0.120ns、仅1失败。唯一失败为DDR group2 dq_loop[7]/ICLKDIV → rddata_r1[63]/D，net `_N199`，CR1:CLMA_351_702 → M2:CLMS_351_709，fanout1；该端点slow hold+0.181ns，精确setup slow/fast +4.735/+5.747ns。摄像头输入保持失败已全部消除。recovery slow/fast −3.869/−2.926ns，245/231失败；removal +0.303/+0.023ns，MPW +0.035/+0.035ns，均0失败。仍不能上板。

r4从新d3报告生成范围；q4原生精确查询与全路线导出54.608秒通过，路线16,828条。p4基于e4/q4/原厂同配置来源重新证明完成：127独立源端点对，两角各245逻辑检查/252原生变体，17,937原语中的注册sticky入口及内部126目标通过，未应用任何豁免。p4 SHA256 `5ca3eb87d02ae1bba1474f35babbf3c1cf2ab538f09d3915394fc90d7ee978ff`。

a4-request.json只请求上述单分支，所选未占用原厂连线为ZDNE[0]:SRB_330_738→IDNE[0]:SRB_336_744，绑定a4-waypoints.json、h3、q4和p4；当前正在完整prepare校验，实际修改、重新STA及effect验证尚未完成。新run_raw_camera_delay_route_reset/derived_inspect与audit_raw_camera_delay_reset_effect限定当前候选，41项相关测试通过，真实h3四条精确case可解析。不能把工具测试/证明成功写成时序闭合。

### 2026-11-01 a4保存与e5最终时序通过

a4实际局部绕线和127对限定复位约束应用完成，59.421秒、exit0、来源无漂移。`a4/input.adf`与`saved-reset.adf`同SHA256 `6f8d2f9fd30a1f460d84b3fcc25af9075cc1cde4bf666ce66e378d5bdf85cba7`。e5独立进程重新STA及功能网表导出89.327秒通过，q5最终原生IO查询44.53秒通过；两者exit0、来源无漂移，没有生成位流或访问硬件。

e5双角十类检查全部零失败。slow setup/hold/recovery/removal/MPW最差分别+1.311/+0.059/+3.415/+0.354/+0.035ns；fast分别+3.645/+0.020/+5.572/+0.023/+0.035ns。精确DDR目标slow setup/hold为+3.704/+0.770ns，fast为+5.134/+0.308ns。这些是完整原生STA结果，不能代替最终修改范围、IO/CDC、位流及实板验收。

effect审计发现两类原生保存/报告差异。其一，PDS保存时将`(FILETABLE (FILEMAP 2 ""))`变为`(FILETABLE)`，只允许删除空源文件名，非空映射删除/变更及新增均拒绝；source行号元数据前后留档。其二，唯一fast hold目标的最差数据沿由三个r变为三个f，未改物理链上的上游net/单元弧和末端hold弧随代表变化，不能强称只有_N199的数值改变。

新增窄分支要求全功能/FF位置、非目标路线、时钟、精确约束与全部STA检查先通过；限当前源端点、_N199、fast hold及r→f模式，核对全部累计、logic/route总量、hold/required和slack算术，其余三个case继续严格只允许目标net延时变化。结果明确`NativeWorstTransitionRepresentativeChanged=true`、`SameTransitionVariantProved=false`、`OnlyRepairedNetDelayChanged=false`。当前正在完整重算effect，成功后用e5/effect/q5生成新io4；io3为旧基线且绑定旧工具，不能充作最终证明。

完整effect审计已通过，`effect-a4.json` SHA256 `a485f2100c05448b9b1582451c94717516bea8bb35299f309b37dc6b60c783cc`，408项输入绑定。17,937原语/6,963FF功能与位置不变，16,828条路线仅_N199改变；5条新增false-path恰覆盖127对已证明复位端点，数据false-path为0。新代表切换17项正反测试和既有effect/filetable 21项测试通过；io4正在对e5/effect/q5进行完整最终重核。

io4最终审计通过，`ScopedDigitalChecksPassed=true`、`Blockers=[]`，SHA256 `025fad369a8ab1d4ef9e39b5f43d7561323fd324424ff50e56c7fdcc14601967`。128项最终原生pad映射、8位输入延迟、20Gray/10标量/6复位链/34held数据及双角各60条max-delay路径完成核对，最大到达slow/fast 1.660/1.032ns。外部AC、模拟MTBF及原生电气设置仍是独立未签核项。

已建立`bit-d3-a-request.json`，明确绑定d3计划、a4 ADF/回执、e5导出、effect-a4和io4；离板批次`release-d3-a.py`正在执行当前证据全量重算→fresh STA→运行时检查→位流生成/核验→仅准备SRAM计划和pending采图绑定。流程不调用program.execute，不访问硬件；仍须取得用户新的上电确认。实际完成状态须以bit-d3-a/verification.json及program-d3-a/plan.json为准，不能把启动当作生成成功。

上板观察须使用本采图版的LED定义：LED0心跳、LED1相机初始化ready、LED2 HDMI初始化ready、LED3 PLL lock、LED4相机配置错误、LED5 HDMI配置错误、LED6预览ready、LED7原图采集失败。LED5/6不再是显示版的采集/处理计数灯，不能继续要求它们一起闪烁。相机及DDR就绪后还有8秒采图预热；初次UART接收仍按90秒上限处理。

### bit-d3-a离板完成，用户重新上电

bit-d3-a实际执行512.493秒，exit0、InputDrift/Diagnostics为空，fresh STA十表/时钟/全部例外与e5一致，位流Verified=true。SHA256 `292b755c8bdf5f16e8697b87fc1c9ae1dbb342226404c9f647eb27030b501fa3`、3,791,112字节，header为2026-11-01 00:29:02。program-d3-a/plan.json及binding-d3-a/validated-build.json、binding.pending.json已准备，四项连接声明此时保持false。

43文件与422本地依赖引用封存到results/raw-camera-ready-20261101-a，manifest SHA256 `ef6898860a20aca6c61ad1eaa785def90cfb1b9c53b9db970920958ba1dbc39b`，复制读回和绑定哈希重核通过。封存是上板前状态，未改原件。之后通知用户上电，用户已回复“已上电，继续下载”，当前执行program-d3-a；须读取最终receipt.json才能判断下载成功。实际重新枚举CP210x UART为COM7，VID10C4/PIDEA60/serial0001，见uart-port-20261101-a.json，未打开FTDI COM5/6。

program-d3-a实际SRAM操作于2026-11-01北京时间00:36:17–00:37:19成功，Passed/Executed/DoneConfirmed均true，FlashWritten=false、CleanupErrors=[]，scan/program原生日志通过，结束无自有JTAG进程。位流仍为292b755c…b501fa3。用户上电确认只用于本次会话；后续断电需新确认。当前connection-review-20261101-a.json记录同一已工作CAM2接线、128脚原生映射及本次用户上电依据，未宣称物理电压/电气/外部AC实测。capture-first-d3-a.py正在生成binding-live-d3-a，再只读接收COM7的一帧；结果将保存在first-frame-d3-a，不把脚本启动当作图像通过。

### 首张实际原图通过，待采棋盘

binding-live-d3-a/binding.json已绑定同一位流、本次成功SRAM回执、接线复核和98项真实来源，复制到work/camera-vga-calibration-20261031/binding.json后逐字节一致。COM7只读921600接收于北京时间2026-11-01 00:42:58取得frame50（固件采集事务号，非传感器曝光计数）：640×480 RGB565_LE、614,400字节，头/源端/读回CRC通过，source/host CRC均BF79B08F，0拒收包。启动时丢弃103,113个字节用于找到下个完整帧头，非完整帧CRC错误；无剩余半帧，无超时。原始文件SHA256 3d64ef74a7067711f85284a3fc85f01c790ec3a6400a4ff6078d29d44a696981，PNG SHA256 3fec080aaaa4f612ae7ce30da767441b13cd45404336b2cf5261a25a8c4dadb5；独立raw CRC及RGB565→PNG逐像素核对通过。

原图为清楚的室内桌面场景，存在明显广角曲线，未出现棋盘；静态图看起来正立，但左右及实时HDMI预览仍待用户反馈。此帧只证明原图采集，不计入训练/留出，不是K/D标定。证据在work/raw-camera-upright/first-frame-d3-a；进度在work/camera-vga-calibration-20261031/progress-20261101-a.json。采集进程已正常退出，摄像头板卡继续运行。已通过异步问题请用户摆train-01：中央正对镜头，约占画面一半，完整棋盘及边缘可见；收到摆好确认后先稳定10秒，再用capture_one.py默认的新binding执行，不能凭时间过去当作用户已摆好。

首次上板/原图证据另封存到results/raw-camera-first-frame-20261101-a，15项文件、2项本地像素引用，manifest SHA256 `4d7de4c6f821bb5e61dcc904d963779809f21ed66c5aba63a9191967fcf44305`。原始场景像素和PNG没有复制到results；保留work原件与哈希。所有新采图开发/封存仍为本地未提交，不能声称本轮已推送。

用户后续确认“预览正立、左右正确且持续更新”，并已完成train-01/02/03三次不同摆放。三张均54内角点、0接收拒包、无质量警告，分别frame282/313/343、CRC D3987120/E959353B/A1CABCC6。当前等待train-04右侧摆放，实时选中列表/覆盖计数与后续进度见[采集进度](CAMERA_CALIBRATION_CAPTURE_20261101.md)，不再在本历史文档逐帧堆叠。用户问显示变糊，已解释HDMI仅160×120降采样预览，标定UART原图仍640×480。
