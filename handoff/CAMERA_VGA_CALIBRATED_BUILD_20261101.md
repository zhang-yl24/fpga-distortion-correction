# 当前镜头矫正候选构建（2026-11-01）

用户明确“开发板已断电，继续”。当前只做离板开发；旧SRAM配置已失效，之前live binding不能用于新一次硬件访问。准备好上板时先通知用户，等其确认重新上电后再下载。

候选`camera_vga_calibrated_top`从已验证的upright显示工程派生，固定640×480、HDMI1080p30扫描、gamma旁路、旋转0°。相机方向初始化、DDR、控制/复位、输出链路不变。新增已验证的8路1.5ns输入延迟；13项整数配置来自本次镜头f240映射，radius guard11610104。不能把HDMI扫描率当实际处理帧率。

标定来源与范围见[标定交接](CAMERA_CALIBRATION_PROFILE_20261101.md)。右下硬件遮挡区仍没有光学验收；输出收窄视野，不能恢复遮住的场景。

新文件：

- `distortion/board/camera_vga_calibrated_top.v`
- `distortion/board/camera-vga-current-lens.vh`
- `distortion/board/camera-vga-calibrated-sources.json`
- `distortion/tools/prepare_camera_vga_calibrated.py`
- `distortion/tools/run_camera_vga_calibrated_diagnostic.py`
- `distortion/tools/run_camera_vga_calibrated_inspect.py`
- `distortion/tools/audit_camera_vga_calibrated_reset.py`

新closure109项源、29个显式design（含1IDF）、74个IDF展开体不重复添加、5个header。继承原128脚及相同FDC/RCF，输入min0/max5ns、正沿采样不变；没有导入旧DDR路由修复或复位端点例外。

已过准备/拒绝测试23项、只读检查边界15项、复位scope适配10项。旧已封存工具和生产RTL未改。

## 本轮执行

`distortion/work/calibrated-camera-vga/build-a/plan.json` SHA256 `2679a1f829d1fc5bad5367c84fa69d7c0347e2813c2ceeba7ffa0df29fed593e`。

2026-11-01北京时间02:44:28启动PDS离线流程，1800秒上限：compile/synthesize/map/place/route/route optimize/report timing。没有请求位流或硬件。过程日志`execution-stdout.log`，最终以`execution-result.json`实际状态为准。

真实当前相机原图的逐像素回归在`distortion/work/calibrated-camera-vga/replay-a/`，使用独立整数参考、相同标定参数及guard，真实处理/读回/FIFO/扫描。最终回执已通过：614400个坐标及614400个DE/RGB像素逐项一致，两帧CRC为B333AEAA、0601182A，欠载0、CRC错误0；输入/源码/fixture哈希前后一致。正式报告SHA f2679208feb33ce1a1dc124c779c609e64e67b62670a33c10870d52bf0c715aa。

回放封存`distortion/results/calibrated-camera-replay-20261101-a/`共41项文件、其中29个工具/RTL快照，manifest SHA c0fedbd4dd523ce28b252b756785272dbfe2be7356d445ce288a8a5a76ccfb88；README快照数量笔误33已在新包首次外部引用前更正为29。源像素仅留本机。回放未覆盖实时摄像头、生产bank manager并发、物理DDR/HDMI或FPS。

构建结束后读取双角十类时序和资源。按新ADF批量导出原生网表，枚举当前复位/CDC/输入延迟扇出；任何失败只按当前证据修复，不能套旧_N199、旧端点数或旧fast seed。无源漂移、IO/CDC、时序、实际RTL和位流绑定全部准备完成后再通知上板。

当前新候选尚无时序验收、位流或实屏结果；新开发未提交/推送。

## build-a 实际完成与当前复位证明

PDS于北京时间02:56:38干净结束，729.649秒，NativeExitCode=0、SourcesStable=true、InputDrift=[]、全部阶段与cleanup完成。最终ADF和pre-STA快照SHA均为`161b3618ec2d229ca872414a7507160f2972f997449362a738db1dc9bbda8446`，STA前后字节一致。

原始双角setup/hold/removal/MPW均0失败，setup最差slow+0.367ns/fast+3.131ns，hold最差slow+0.060ns/fast+0.014ns。失败全部为DDR recovery，slow245/fast232个逻辑检查失败；每角245逻辑检查、252原生变体，5源127精确源端点对均从本次报告重建。不能套旧路由修复。

`export-a`已原生重新STA和导出带位置网表，114.732秒、exit0、来源无漂移。`reset-query-a`61.112秒、exit0，实际pin names/count符合本次scope。其未执行前dummy.v由CRLF规范为校验器要求LF；未修改已绑定inspect工具。`reset-proof-a/proof.json` SHA `c37df905e1fde2e8159ca3ac6e7399800fca52ba91274eadf8ba0d0caa63bc31`：入口/内部连接及同配置vendor字节证明通过。约束尚待独立副本应用和效果核验，不是完整时序验收。

新增reset-only physical/derived_inspect/reset_effect工具拒绝所有route-reset来源；77项相关测试通过。另新增IO/CDC native补全工具及19项测试；batch把精确路径查询、IO位置及route dump放在同一原生进程。

实际摄像头延迟图存在直达capture FIFO的DRM36K DIB向量端口，原检查器只接受标量FF而正确拒绝了未知表达式；正在针对实际原生RAM配置完善严格图解析。尚未获得完整IO/CDC验收。

## 输入延迟完成与reset副本

输入延迟审计按本地原厂V_DRM36K_E1模型确认SDP64 DIB写入使用CLKA正沿，严格展开36bit向量并拒绝奇偶位/其他配置/旁路；30项测试通过。实际export-a枚举173个唯一首级采样端点（165FF+8DRM数据位），8路延迟全部必经，全部camera_pclk；这是结构扇出上界，不是布尔敏化/外部AC证明。工具SHA93720a6f5fa02752e9b94307add8a0c8529458464e1110d2c583c3b6c90fe6b0。

reset-apply-a执行干净结束，67.001秒、exit0、InputDrift=[]，得到ADF `b209084fb357f2bb349a2835c6f23c2fc701df737d16671ebdc93f0135b58c4c`。只保存本次精确reset范围；final-export-a正在独立进程重新STA/export，尚不称时序通过。板卡仍断电、未访问硬件。

## final-export-a 已完成

117.599秒、exit0、InputDrift=[]，原生十表全部0失败。最差slack（ns）如下：

| corner | setup | hold | recovery | removal | MPW |
|---|---:|---:|---:|---:|---:|
| slow | .367 | .060 | 1.679 | .311 | .035 |
| fast | 3.131 | .014 | 3.866 | .060 | .035 |

最终结构审计`io-final-structure-a`通过：34 Gray bits、22 scalar chains、7 reset chains、28 replicated reset second stages、128脚。需要35对精确interstage查询及10对报告未覆盖的Gray补查；最终native query已准备中，不能以结构通过替代实际延迟覆盖。

baseline-route-a原始路由只读导出74.827秒、exit0、无漂移；后续final-query-a同时导出副本路由并补全IO/CDC，以便reset-effect逐路比较。新增calibrated bitstream工具35测试通过，program工具9测试通过，均尚未请求实际位流或硬件。

## final-query-a 已完成

最终原生补充查询173.423秒、exit0、InputDrift=[]、Diagnostics=[]。4组时序查询覆盖计划中的35对interstage与10对Gray缺口，128个IO site查询及最终route dump均已生成；正在由CPU严格验收每一对/每一corner/kind和复位效果，不以执行退出0代替路径覆盖通过。

后续原始inspect query准备需注意：已冻结inspect.prepare在Windows写dummy.v为CRLF，而validate要求LF。只允许对尚未执行、内容恰好为预期占位模块的dummy.v转换为该确定LF字节；验证器会再次逐字节核对。已封存inspect源码不能临时修改，否则当前receipt绑定失效。derived_inspect的写法已使用newline=LF，无此问题。

## 最终IO/CDC原生验收通过

`io-final-native-a/io-cdc-native-proof.json` NativeAuditPassed=true：35对interstage的140个corner/kind case齐全，最小setup+5.895ns/hold+0.187ns；34 Gray bits的68个corner case完整，最大到达0.994ns；128脚实际native site及functional pad映射均通过。8路输入延迟173个采样端点图绑定在最终证明中。外部AC/模拟MTBF/长期运行仍未签核。

## reset-effect-a 与位流流水线

`reset-effect-a.json` SHA `5cfbed6da1f65de1740ad45598c0a9c2b71303a672077380b70f8559538a4697` 已通过：33703条路由全部相同、36485功能单元和17353FF位置相同，精确复位例外联合及所有其他例外一致，没有setup/hold数据false path，十表全过。`io-final-native-a`证明SHA `cd89679335ffc1d85c1fa5204d43fd693cd65a7de6ac74d4ecb6f532fe9c3f1a`。

`bit-request-a.json` SHA `d944e3f766668aa1b0f915496ff5af6668fcaea3487fbd45f585790b27b72ddb` 绑定上述当前ADF/最终export/IO proof/application/effect。`offline-build-and-plan-a.py`当前正在同一进程完整authority后prepare bit-a、execute fresh STA→CPU gate→genbit→verify，再仅prepare program-a。只复用本进程已完整审计且每次全哈希复核的缓存，不沿用历史fast seed；独立gate子进程仍重算完整authority。未执行任何SRAM下载、UART或JTAG；板卡断电状态保持。

位流流水线已完成首次完整authority复核并prepare bit-a，计划绑定484项输入，900秒native上限。PDS本次fresh Report Timing已完成，独立CPU gate正在重新复核和逐项比对报告，尚待Generate Bitstream/最终verify/program准备回执。不得仅凭Report Timing done要求上电或下载。

## 当前离线完成状态：等待新的上电确认

北京时间2026-11-01 03:39:05完成全部离线工作。bit-a的fresh STA→独立CPU gate→Generate Bitstream→verification通过，native 463.137秒、exit0、无漂移、无错误、未超时，父进程正常退出；随后进程列表无python/PDS残留。没有硬件访问。

- 位流：`bit-a/generate_bitstream/camera_vga_calibrated_top.sbit`，3791112字节，SHA256 `4c0ee8dca7aa168b4f1c760408f9e65bb21a0fd42b664c1632215bb28ce5bac9`，header 2026-11-01 03:38:23，PG2L100H/-6/FBG676。
- 最终ADF：`b209084fb357f2bb349a2835c6f23c2fc701df737d16671ebdc93f0135b58c4c`。
- SRAM计划：`program-a/plan.json`，SHA256 `f9ccb035e312f6a71240767f50fbe687fbee533fc2dce429c60db95287bd43ad`，501项绑定输入，仅volatile SRAM；已完整prepare，未execute。
- 机器回执：`offline-ready-a.json`，HardwareAccessed=false、BoardPowered=false、HardwareCorrectionVerified=false、FlashWritten=false。
- 可移植封存：[calibrated-camera-ready-20261101-a](../distortion/results/calibrated-camera-ready-20261101-a/README.md)，180项文件（148个来源快照），manifest SHA `126da1decd7fb36d94d48fb1a8ac5901a5c85150c475c56bdaa07c900ebec540`，全部回读一致；大型ADF/网表/路径报告只做本机哈希引用，私人像素未入包。

下一步通知用户上电，保持OV5640和HDMI OUT连接。只有收到新的“已上电”确认才使用新program-a计划执行，不沿用旧live binding。下载后先观察棋盘/门框直线的矫正效果、正立/左右正确/持续更新，及LED5/6闪烁、LED7常灭。无需重做18张标定采集。不声称实屏矫正、有效1080p、实测FPS、外部AC或长稳已经完成。新成果仍本地未提交/推送。

## 新的上电确认与下载执行中

用户回复“已上电，继续下载”，当前按已上电处理。已启动camera_vga_calibrated_program.py --plan <绝对program-a/plan.json> --execute --board-powered --user-notified --timeout-seconds 90。仍先完整重核证据，然后仅执行易失SRAM下载。独立只读检查已重核501项输入和封存180文件、目标PG2L100H/0x00602899、JTAG1MHz、Tcl无Flash命令，全一致。此时尚无成功回执，不声称已下载或实屏矫正通过。

## program-a 实际下载成功：等待实屏观察

2026-11-01北京时间11:55:07–11:56:15实际执行成功（完整CPU复核先于此时间）。PG2L100H / ID0x00602899识别正确，JTAG1MHz，原生Program31.0秒、done bit=1，status done_i=1/done=1。receipt Passed=true、ProgrammingAttempted=true、DoneConfirmed=true、FlashWritten=false、CleanupErrors=[]；扫描后的JTAG服务按已有受控流程重新启动，全部自有进程结束。

位流SHA `4c0ee8dca7aa168b4f1c760408f9e65bb21a0fd42b664c1632215bb28ce5bac9`、最终ADF `b209084f…5b58c4c`，与本次已核验计划完全一致。501项绑定输入及所有日志再核一致。

实际回执`distortion/work/calibrated-camera-vga/program-a/receipt.json`，当前机器状态`downloaded-state-a.json`。16文件下载封存`distortion/results/calibrated-camera-download-20261101-a/` manifest SHA `1e6712b39406618411117c290927259ea22c1cc4b21ee90c0ad4dbf333102125`，全部回读一致。先前offline-ready的BoardPowered=false/HardwareAccessed=false是离线历史，不能覆盖本次实际下载。

已请求用户观察：棋盘/直边中央和稍偏边缘是否比原先更直、画面正立/左右正确/持续更新；LED5/6是否闪烁、LED7是否常灭。反馈尚未收到，HardwareCorrectionVerified=false；不追加采图任务，不调参数直到获取当前实际反馈。

## 当前阶段完成：用户首次实屏矫正确认

用户在本次下载后回答：

- “画面正常更新，直线明显变直”
- “LED5/6 闪烁，LED7 一直灭”

因此本次实际镜头640×480矫正已完成首次实屏定性观察：直线改善、实时更新、采集/处理活动及故障灯未置位。简短选项回答未单独重确认上下/左右方向，不能编造该项新观察；此前正立配置未变。

`live-observation-a.json` SHA `9c0bb54238e6ba92b9abca6d9c5fffa04cadb3befbbaa6311da1fcbe0c793864`保存原话并绑定本次program receipt、位流及ADF；`current-live-state.json`是当前状态。三文件可移植实屏封存`distortion/results/calibrated-camera-live-20261101-a/` manifest SHA `b00f9a72c60aa2f78ed8e2caa61d1ccfa17282446d63fc62abbef73a5ece1812`，全部回读一致。早先downloaded-state/下载封存内待反馈字段保留当时事实，由此新记录覆盖，不篡改历史证据。

当前镜头畸变矫正这一优先阶段已得到首轮实板效果；后续按用户顺序再讨论实际帧率测量、性能优化和1080p输入升级。不能把HDMI1080p30扫描当有效1080p或处理30fps，当前有效相机分辨率仍640×480。本轮没有实板逐像素采图、长稳、外部AC/模拟MTBF证明，右下物理遮挡区仍未光学验收。

板卡最后确认上电、配置为易失SRAM；下次用户断电后必须使live状态失效并重新下载，不沿用DONE结论。新开发/标定/封存仍本地未提交推送。

## 当前矫正版人工帧率测量

用户按LED6第1次亮起至第11次亮起（10完整周期）反馈“依旧是13-14s”。当前LED6=processed_frames[4]，每周期32完成帧，故320/14=22.857fps、320/13=24.615fps，约24fps。绑定本次位流4c0ee8dc…ce5bac9，记录`frame-rate-observation-a.json`，可移植证据`distortion/results/calibrated-camera-frame-rate-20261101-a/`。

与旧版本人工测量区间相同，未观察到明显帧率下降；不是严格零开销证明，未定位摄像头/处理/DDR/显示瓶颈。该数值是处理完成帧率粗测，不是精确仪器测量或显示独特新帧数。HDMI仍30Hz扫描，不能将其称处理30fps。无需为记录此次测量重新下载或访问硬件。

## 本次仓库同步范围与提交前检查

用户要求把当前成果推送仓库；本次提交包括采图依赖、当前镜头标定与反解修复、矫正候选/工具、已验证位流、两帧回放、下载/用户观察/人工帧率记录。提交前新增及受影响CPU回归429 passed、30 subtests passed；原有四份基线来源闭包审计通过；新增8份成果包共341个文件的manifest逐项回读一致。私人相机像素和大型构建中间文件未加入本次提交，记录只提供本机路径和哈希引用。

同步分支使用`codex/camera-vga-calibrated`，从与VGA正立交付相同树的origin/main开始，保留已完成阶段为回退点。后续任务明确改为先1280×720有效输入/矫正，再在720p基础上提升帧率，见[720p任务顺序](CAMERA_720P_NEXT_20261101.md)。实际远端提交以Git引用为准，以上各阶段“未提交”描述保留当时事实。
