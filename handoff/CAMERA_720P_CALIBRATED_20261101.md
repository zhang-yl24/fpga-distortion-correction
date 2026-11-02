# 720p 当前镜头矫正候选（2026-11-01）

## 23:34最新结果：720p矫正位流已下载，等待用户返回实屏确认

`program-a`在北京时间23:31:15–23:32:35实际完成：Passed=true、DoneConfirmed=true、FlashWritten=false、CleanupErrors=[]。板上当前配置已变成`camera720_calibrated_top`，不再是VGA原图。用户已反复授权检查通过直接下载，本次执行前已通知；用户离开数小时，尚无新实屏/LED/FPS观察，不发送批准或摆拍请求。

`bit-a/verification.json`为Verified=true，实际位流3791112字节，SHA **184c689c0bedf01d5f79912fdaf9e19cbd26db0d8b2999dc4bd74ecfbff43f86**，header时间23:23:45，目标PG2L100H/-6/FBG676。生成前`bit-authority-a.json` SHA `91a33d2e54deed3e6ee9201e126a42811a560ac227a210db7df5dfb388fb51e8`完整复核1088项输入；生成阶段重新STA、比较十表/时钟及全部例外，再允许gen_bit_stream，ADF字节不变。仅作为当前镜头开发检查点，未扩大外部AC或光学范围。

最终`reset-effect-a.json` SHA `8f2e1563bd75dd1fe0592d542b3f336e43c99768de68981bc874df022ac06d5d`核实精确复位集合、全部功能/放置/布线与未受影响时序；最终`cdc-final-proof-a.json` SHA `88cefc39d183a31583c25f6dfaab0b6e8bb6bb4083b87eb352536841d38e4f6f`覆盖2486/2486（2070跨域max+208setup+208hold），0missing/violation，816输入。128引脚/电气、DVP40/40、TX56独立max案例齐全；CDC最差+0.173ns、条件DVP最差+0.023ns。两者都基于最终f0015…候选自身新报告，未借用旧目标的时延。

原52条Sdm缩位诊断与原失败回执保持原样。新的位流provider显式限定接受已逐个解释的公开计数器上界、同源同配置的受保护DDR工程依据，用于当前开发候选；没有声称受保护计数器形式等价或清除了原诊断。原native metadata失败也保留，并由独立完整路线/语义重新审计接续。

下一步：精简封存本版和回退文件，然后构建隔离统计候选以自动测量帧率。统计源码/115200 UART解析及只读接收已通过离线测试，`camera720-calibrated-stats/build-a`仅准备计划，尚未EDA或下载。此版720p矫正的实屏直线、方向、持续更新与LED观察等待用户返回；实际帧率仍未知。以下均为历史阶段记录。

## 22:24进展：最终候选双角十类内部时序全部通过

`final-report-a`真实新进程通过，80.816秒，回执SHA `b8c9162351215b3ce19f0de0c241eb6db86aec98a4132f32f2c83e2ac0e15484`，绑定最终ADF `f0015b1c…e5c14f2e`；实际完整时序报告SHA `be2d05829d7046d82072d8135e3041699d9520ca11a40f30fc81e3d05e21a206`。

| 类别 | slow最差余量/ns | fast最差余量/ns | 失败数 |
| --- | ---: | ---: | ---: |
| setup | +0.430 | +2.982 | 0 / 0 |
| hold | +0.061 | +0.020 | 0 / 0 |
| recovery | +3.211 | +5.087 | 0 / 0 |
| removal | +0.309 | +0.028 | 0 / 0 |
| MPW | +0.035 | +0.035 | 0 / 0 |

`final-export-a`正在原生执行。随后仍须独立复位效果集合及最终CDC/IO，不把STA摘要当作这些审核已完成；尚无新bit或下载。并行新增的核心域UART统计仅是后续实验模块，未集成当前冻结候选，未取得实板FPS。

## 22:13进展：精确复位应用完成，等待最终STA/CDC

`reset-apply-a`实际通过，138.298秒，native exit0、无关键诊断/输入漂移；回执SHA `eecd424d2ebeaa34fac3fef507ce5cbcdbff913f43b799379a7cd671293af4ab`，新候选ADF `f0015b1cc7f37eed15841a650a87f077c5dedc8dd8d0495331d0bb78e5c14f2e`。本次重新核对127个来源/目标和5组限定复位命令，实际原生命中名与预期完全一致。应用后35046条NETANNOTATE、所有target trees、所有非约束语义、FILETABLE均不变，仅增加预期类型的约束引用；约束的最终效果仍待新STA与精确集合审核。

`camera720_calibrated_final_inspect.py`使用一次完整source验证后显式SHA绑定的authority，每个报告/查询仍逐文件核对全部输入/工具/ADF/原生名，避免每批递归重解析同一大型报告。新进程最终report/export及最终CDC/IO尚未完成，不能写成可下载。用户离开期间继续自动推进，不请求实屏反馈。

此前GitHub失败涉及的两个测试fixture已本地修复，不修改生产native检查；30项测试和25子测试通过，Linux Actions尚未运行。证据见`distortion/work/camera720-ci-fixture-repair-note.md`。

## 21:55进展：DDR hold修复后双角通过

独立`route-reassessment-a.json`已实际完整重算通过，SHA `4c66c5b7330f617d6e68ce85b169f28ed5e7bdf1f8658224886b375e67ffa6c9`。35046条路线中仅`_N177`改变，其余路线、功能/布局语义、全部CDB定义及按父对象的引用保持；只确认空FILEMAP2及20836对数字FILEID/LINENUM源位置元数据被PDS保存删除。原failed receipt未修改。

新进程`physical-report-a`实际通过，78.67秒；slow/fast setup **+0.430/+2.982ns**、hold **+0.061/+0.020ns**均零失败。recovery仍245/235失败，须按已逐端点核验的复位结构处理；removal/MPW仍通过。root已启动`physical-export-a`导出同一修复后网表，随后精确复位与最终CDC/IO。尚未生成/下载720p矫正版。

用户再次明确“已上电，可以直接下载，不用等批准”，随后说明未来几小时离开、回来会告知。保持自动推进，不再发批准/摆拍/肉眼检查请求；可自动检查与SRAM下载继续，实屏光学观察保留为用户回来后的未完成验收项。当前top无UART遥测端口；DONE只能证明配置，不证明实时画面或FPS。

## 21:42进展：DDR支路已保存，正在精确复核保存元数据

root执行`physical-route-a`，native exit0，159.483秒（含CPU比较），新ADF `826441df556ae5e4e1541b2a5efa55e420f80abaade153fb91bfa0355fec55c4`；无原生关键诊断或输入漂移。严格回执仍`ExecutionPassed=false`，SHA `f5c7a2e4df273a54a8bd72682153eb51578ac0d9e4df016a8180c0fed42cb489`，原件保留。拒绝项为PDS保存时将`(FILETABLE (FILEMAP 2 ""))`变为空`(FILETABLE)`；独立工具正在核对这一精确元数据变化以及全部实际连接/布线语义，不能直接跳过或改写原失败。保存成功不等于hold已消除，下一步必须fresh STA/export。

原候选IO实测已完整覆盖128个引脚、电气参数、40项DVP与56项TX目标路径。当前图CDC重新派生18159FF、979逻辑关系和2486适用检查，未使用旧图计数；最终布线/复位结果须重新采实际延迟。新位流及SRAM入口已开发，但尚未具备最终候选证据、没有生成/下载。后续优先完成单支路修复验效、精确复位应用和最终CDC/IO。

持续上电和检查通过后直接下载的会话授权仍有效；当前板上仍VGA原图版，本轮无需更多棋盘采集。以下为历史阶段记录。

## 21:16进展：实际镜头完整系统仿真通过，处理新候选物理时序

本节覆盖下文“尚无原生完成结果”。`camera720-corrected-system/actual-lens-rtl-a` 已实际通过完整两帧系统仿真，1521.699秒，1843200个扫描像素逐一匹配独立参考，零欠载/像素错误、最终排空完成；使用本候选header `01c797c6…b9e4a`，源CRC `DF5734A7/73964307` 与矫正结果 `A3201F8C/C951D8CC` 分开校验。报告SHA `e0f38ae39f43a5088896c9cd34dbeaa486c92297835259852abda8885814d76c`。这是数字仿真，不是实板FPS或实屏光学验收；不需无因重跑。

原生build-a实际完整执行750.299秒，exit0、源无漂移、STA前后ADF相同 `71bea98abdbc80cdf2a9af86f60e76e9b49dd4c52d1c62b08f10cf5ce8b9d66a`。52条Sdm-3003（四份日志各13事件）使严格原始receipt维持 `ExecutionCompletedWithoutError=false`；11个公开计数器事件的实际界限与两个同源同配置受保护DDR事件已独立记录，未抹去原失败。只读export-a、hold-discovery-a、reset-query-a原生执行已通过，IO查询进行中。

当前未修复时序：slow/fast setup +0.430/+2.982ns均通过；hold各1处，-0.096/-0.308ns；recovery失败245/235；removal +0.309/+0.028ns、MPW +0.035/+0.035ns通过。唯一hold为DDR组3读回`rddata_r1[62]`的`_N177`单支路，精确setup余量5.132/5.983ns。当前export实际38415单元/18159FF；复位从本报告恢复5组127个来源/端点，网表连接通过，未继承旧端点计数或豁免。下一步只在独立ADF副本修复此支路，再核验复位范围并重跑最终STA、CDC/IO。

板上仍是第三组下载的VGA原图版，新720p矫正位流未生成/未下载。用户已结束本轮摆拍，保持板卡持续上电的授权有效。CPU对照图位于 `distortion/work/camera720-calibrated/previews-a/comparison-cpu-f480.png`，清楚标注不是FPGA实拍；f480输出视场较原广角收窄，原图与矫正图文件均为1280×720。

## 当前截面

实测模式转移及有限范围的独立姿态验证通过，开发用参数、完整720p数值检查、隔离构建源码已经准备。root已启动 `camera720-calibrated/build-a` 原生编译/布局布线/STA（session50523）；**本交接尚无原生完成结果**，不得写成时序通过或已上板。

当前板上仍是第三组配对时下载的 `raw_camera_capture_cam2_delay` VGA原图采集版。720p矫正固件尚未生成/下载。用户持续上电；硬件操作由root统一管理，子代理没有运行PDS、UART或JTAG。清晰度与矫正优先，帧率优化随后进行；新候选不改变现有吞吐控制，未测得新的实际帧率。本轮未提交或推送。

## 真实几何依据及范围

- 沿用已验证的当前镜头VGA标定，fit01得到VGA→720的轴向缩放/裁剪矩阵；第一对54角点RMS0.3310367509px、最大0.9797714519px。
- 第二对原报告残差异常后，用户明确确认相机位移，撤回该对固定前提。失败报告原件保留，既不作为有效held-out，也不据此判定模式几何关系失败。
- 第三对held03在用户声明固定后实采，保持fit01矩阵及RMS0.5px/最大1.5px预算不变，54角点RMS0.3120311379px、最大0.7409819124px；没有用验证对重拟合矩阵。
- 固定转移K/D在该720目标姿态的检查RMS0.2992546507px、最大0.6176820003px。只有1张transfer-held-out，角点主要覆盖左侧及中央；没有新增独立target-only姿态、全视场覆盖或完整光学验收声明。相机姿态和镜头未调仍属于用户声明，并非程序独立测量。

根路径 `distortion/work/camera720-mode-pairs-20261101-a/two-pair-validation-b/`：

| 文件 | SHA256 |
| --- | --- |
| target-validation-report.json | a5a22cdea4a36ff9df35d487cbbd1f41b4fac14cdb7214464ab1c70d64a4a32d |
| target-candidate-freeze.json | fdc4d1ed782b7908f1b2debf1bd61e02825de4f41b8c0241a1174d1b2cd33267 |
| paired-transfer-report.json | d53d18ceab79d49c5fcfaf3c8bac5663e6f1735bcdcd612dfc88bb0b74121c65 |

`pose03-user-confirmation.json` SHA256 `1f34d102c56275f8a3541e84a241f757a1cb6f0b777d574a1bc9d2b34a97b3b9` 包含位移原话及第三组固定声明；开发profile保存其完整内容和来源哈希。旧VGA源profile SHA256 `94181c07a4456f511853f51022eba1b55965b115e1569f3fcbad460a2d92999e`。

## 开发参数与完整数值检查

`distortion/work/camera720-calibrated/inputs-a/` 中：

| 文件 | SHA256 |
| --- | --- |
| development-profile.json | f79c44d9bdeb5b114441e53d172d2b22667ba415717dc3a49a4b0a73e15200e8 |
| mapping-f480.json | 563e47ded2488badd2ca626a774c688c1cc4e88d5f435dbaefd9f6e93fd81b50 |
| request.json | 560509e4d990a5f01f40b9c6f2a6b3364f1ad3d079c52211c2e13868e850f94f |

profile为真实图像模式转移所得的显式development profile，不是新独立全镜头标定。`development_only=true`；`passed`、`candidate_ready_for_profile_review`、`independent_spatial_coverage_passed`、`optical_calibration_accepted`与`hardware_release_allowed`均为false。

原 `wideangle_mapping_audit.py` CLI核对1280×720全部921600坐标，stride1、0°、输出f480、中心(639.5,359.5)，预设误差预算0.25px/邻点范围比例0.99。实际最大坐标误差0.0651664845px、RMS0.0207807751px；所有双线性插值邻点均在原图内，零算术溢出/无效、零折叠。半径上限由实测9797640加2得9797642。该数值结论不扩大已观察的光学区域。

## 隔离构建

新 `prepare_camera720_calibrated.py` 保持既有720transport源码冻结，仅在独立work中替换top模块名、include路径和13个signed参数/半径。摄像头前端、1280×720尺寸、输入延迟、8秒稳定等待、DDR与帧缓存、时钟和吞吐控制均继承原源码；旧路由修复、复位例外及硬件许可不继承。

准备器已实际重算target validation与全921600数值检查，生成 `distortion/work/camera720-calibrated/build-a/`：171项输入哈希及全部新源码哈希回读一致；112个compiled输入，31个显式设计，IDF子文件不重复添加。

| 文件 | SHA256 |
| --- | --- |
| plan.json | 6774df13e1b0d3b2ad4d91764b59383c235437c12ede58c4c9bef5e007f36548 |
| source/board/camera720-current-lens.vh | 01c797c6f5e327dae6977c8738ea472551f2f715b415784eaa52ffd2019b9e4a |
| source/board/camera720_calibrated_top.v | 1644d63b447fb55778058d239cae40939a79f79d95836f9c78f10b6d18b85588 |
| source/manifest.json | c3a13c642f2832a87d7cb46f472c869cd48961829d620753e447810691333191 |

冻结工具：preparer SHA256 `b6aeafe2711f6b10e5fe484a422646dd57ae23e68a733f85ec38892c33747e1b`；runner SHA256 `53b86ab0ff54a572cd3a416f3409590da95d7584bd8e7b0e939c2e11725499d4`。定向测试10项与14子测试通过，11.86秒；独立只读审查没有具体阻断。root执行期间不得编辑171项闭包或工具字节。

## 执行边界与下一步

唯一原生入口为 `run_camera720_calibrated_diagnostic.py --plan <build-a/plan.json绝对路径> --execute`，root已经启动，不得重复。runner在执行前重算recipe、核对源码/compiled/Tcl，执行compile/synthesize/map/place/route/STA，要求阶段顺序正确、零C/E/F、输入无漂移及STA前后ADF一致；执行成功不自动授予时序或硬件许可。

已只读核对超时路径：原生PDS使用`shell=False`和Windows `CREATE_NO_WINDOW`；默认上限1800秒。超时、异常或阶段异常只调用已绑定的 `run_camera_vga_output_diagnostic.stop_owned_tree`，以当前仍存活的自有PID执行隐藏的`taskkill /PID ... /T /F`，20秒截止后等待父进程10秒；不按进程名称清理。正常父进程退出不声称独立核实所有后代存活情况。未修改该冻结helper，也未为本次记录额外执行测试。

下一步等待实际PDS结果与当前镜头header的System RTL模拟，随后基于本候选自身网表/布线/STA检查复位、CDC和IO。只有新证据满足要求后才能生成并核验矫正位流、下载及观察实屏直线效果。当前 `TimingAccepted=false`、`HardwareReleaseAllowed=false`、`OpticalCorrectionAccepted=false`；不提前承诺完整视场或新帧率。
