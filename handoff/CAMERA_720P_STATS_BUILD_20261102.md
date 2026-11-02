# 720p 实际镜头矫正统计版

2026-11-02 北京时间。用户离开数小时，开发板持续上电、连接正常，已授权检查通过后直接 SRAM 下载，下载前通知即可。回来前不请求批准、拍照或肉眼检查。

## 04:20 最终统计版实板结果

- 最终候选 ADF：`distortion/work/camera720-stats-delay/repaired-reset-apply-c/input.adf`，SHA `29e2e519cdb7e27ca43209dd57761bd8e70d2e761decbfebf96f5167b311e19e`。
- 完整 CDC/IO 汇总：`cdc-final-proof-c.json`，`ExpectedCases=ObservedCases=2486`，`Missing=[]`，`Violations=[]`，`ScopedDigitalChecksPassed=true`。
- 最终位流工作目录：`distortion/work/camera720-stats-delay/bit-c2`。位流 `generate_bitstream/camera720_calibrated_stats_delay_top.sbit`，SHA `825bbf3920ee8c2d769b0f39a4b11f1c9eddad27247e19d8faeae2bccfaaa952`，3791112 字节；原生生成、STA、例外一致性、位流头核验均通过。旧 `bit-c` 因相对路径 watched-key drift 被严格拒绝，保留但不得使用。
- SRAM 下载：`distortion/work/camera720-stats-delay/program-c2`，`Passed=true`、`DoneConfirmed=true`、`FlashWritten=false`、`CleanupErrors=[]`；使用当前会话已授权的持续上电和下载授权。
- 30 秒 UART：`uart-c2/session.json`，30 个完整包、29 个有效窗口、身份不匹配 0、拒包 0；`SourceAcceptedFPS=15.0`、`ProcessedFPS=15.0`、`UniquePresentedFPS=15.0`。
- 120 秒 UART 稳定性：`uart-c2-stability/session.json`，120 个完整包、119 个有效窗口、身份不匹配 0、拒包 0；三类计数保持 15.0 FPS。当前统计使用标称 125 MHz 核心时间基准；无独立时钟、HDMI 刷新率或欠流标志，不能把该值宣称为 HDMI 刷新率或独立测频。
- 结论：统计版已实际运行，15 FPS 的输入接受、处理和唯一输出计数长期一致；下一步应从输入节拍/帧调度着手分析 720p FPS 瓶颈，再做新的优化候选 A/B，不能仅凭资源余量直接宣称可提升到 30 FPS。

统计版当前已替换板上 2026-11-01 23:32 的无遥测基线：`camera720_calibrated_stats_delay_top` 已通过 `program-c2` 下载到易失 SRAM，位流 SHA256 `825bbf3920ee8c2d769b0f39a4b11f1c9eddad27247e19d8faeae2bccfaaa952`，DONE=true、FlashWritten=false。30秒与120秒UART采集均取得稳定15.0 FPS计数。132文件回退包 `distortion/results/camera720-calibrated-20261101-a` 保持原样，不作为当前板上状态。

## 历史构建过程（以下当前/待完成仅指当时阶段）

本次候选 `camera720_calibrated_stats_top` 保持 1280×720 实际镜头映射、相机配置和视频控制，增加 C24 的只读 UART 统计输出（115200 baud）。`source_accepted` 计数指被接受的输入帧，不等于传感器总输出帧率；另外统计处理完成和独特显示帧。欠载及聚合故障不在同一时钟域，本版明确标为不可用。计时采用名义 125 MHz 核心时钟；CRC 和序号可识别部分坏包与重启，不能证明所有未观察重启都不存在。

历史原统计候选工作目录：`distortion/work/camera720-calibrated-stats`；最后成功的共享延时统计版位于 `distortion/work/camera720-stats-delay`。

- `source-a/source-plan.json`：SHA `ea8884369b13de4db4b40fb1854932ef3d0b61970d3cb47d13bdf88e3b0c481e`。
- `build-a/plan.json`：SHA `61e78a050798723cb04dd7cd5fe54ce2d2e11fe4d32429ff9964c0d2149627f8`，实际构建 732.010 秒，输入无漂移。
- 原生 ADF：SHA `fc1f129f5156f9eaaec135075a18480b2a72d5410798d78d333549bbe22d8460`。
- `export-a/result.json`：实际网表导出成功，119.829 秒；网表 SHA `d866a2e9030a34e68cac737e5f49ae34b653a619345d8910202aff29404119c2`。
- `hold-discovery-a/result.json`：实际路径、站点和全布线查询成功，130.125 秒，无漂移或严重诊断。
- `reset-query-a/result.json`：实际端点查询成功，62.884 秒；`reset-proof-a.json` SHA `548f49da85d430dc9738256817004d746e75983237ef2655305cf559ced64030`，5组127端点对精确匹配。本版重新从39688单元实际图推导，不继承旧版计数作为证据。

原始建立时间 slow/fast +0.423/+2.953 ns；保持时间各16失败、最差 −0.801/−0.667 ns，全部来自 `cam_href/cam_vsync`。实际查询补齐16身份的双角建立时间，最小余量 +11.302/+13.132 ns。拟修复8条实际输入/末端布线分支，保持其他分支及逻辑不变，再重新做全时序。原始 recovery 245/233 失败；复位范围仅提案和名字验证，尚未应用。52条计数器缩位诊断和原始严格失败回执完整保留，单独绑定的有限范围解释不等于编译诊断清零或时序放行。

实际图有444个统计寄存器，完整锥验证均在 `ddrphy_sysclk`、不反馈视频或其他引脚。统计 CRC/字节选择的24个 `V_MUX2` 原语经原厂布尔模型精确支持后重新验证通过；旧解析器不支持该原语的失败记录仍保留。`cdc-query-recipe-a/plan.json` 实际重新导出979逻辑关系、1139查询身份、2486检查项（当前455已覆盖、2031缺失），没有继承旧候选覆盖结果；剩余36命令分5批及1批IO查询。此计划来自原始未修复ADF，仅诊断使用，修复后必须重新导出及测时延。

`native-electrical-a.json` 已从真实路线扫描129个引脚电气参数：UART C24、3.3V、LVCMOS33、4mA、SLOW均匹配。尚待原生site查询和UART输出传播时延。`physical-route-a` 于00:24:40启动独立副本修复8分支，原生阶段限300秒；原候选的66条未选同网分支和其他所有路线都必须不变。布尔锥展开显示8分支影响47个不同FF端口，全部在camera_pclk域，最终完整STA仍需覆盖这些端口和其余检查。

历史原统计候选映射资源：66/240 APM、18692/133200 FF、15068/66600 LUT、16.5/155 DRM。当前上板C版最终物理报告为14948 LUT，见[当前资源核算](CAMERA_720P_RESOURCES_20261102.md)。比矫正版增加533 FF、417 LUT，没有增加 APM/DRM；资源统计不能替代布线、带宽或实板帧率测量。

后续顺序：完成分支修复 → 新复位约束及完整验效 → 本版129引脚与完整IO/CDC检查 → 生成位流并下载 → COM7/115200被动接收统计 → 根据实际接受/处理/显示帧率确定优化目标。统计位流、下载、真实 FPS 目前均未完成。没有本轮提交或推送。

00:26 后续：`physical-route-a` 已实际失败，64.026秒、exit1，第一条 `nt_cam_href` 分支无法经所选远端waypoint接通，报 `E: Manual Route failed`。`_N48` 的内存内操作先完成，但全阶段没有保存候选，`input.adf/post-init.adf`仍是原始`fc1f129f…`，无`saved-route.adf`；不接受局部成功，原失败回执保留（SHA `9a6c796a51ca8cb3cc36bf1e67979ae31e085255a065f70e3d992dfbb618fb38`）。接下来基于实际共享分叉和独立尾段选择新的可达绕行点，独立B尝试；不继续失败进程内存、不改旧回执、不改外部输入时序预算。

00:35 后续：`physical-route-b`（独立near producer）也在同一首条HREF分支失败，64.397秒、exit1、原ADF未变、没有保存候选；回执SHA `853dfa6400b47bda0257663b1bfb32797c656811f193486d6d30366c33d2a48a`。本机原厂手册确认命令合法，但两次具体waypoint不可达，不推断整个共享网络禁止手工路由。

现转向可重新编译的实现修正：新目录 `distortion/work/camera720-stats-delay`，新top `camera720_calibrated_stats_delay_top`。仅在采集支路的HREF/VSYNC增加2路 `GTP_ZEROHOLDDELAY(ZHOLD_SET="1500ps")`，与原8数据延时相同；监测支路继续使用原始控制和像素时钟（监测器没有数据端口），帧处理、镜头映射、时钟及传感器配置不改。正在准备独立源码和build，并用原厂模型验证数据/控制同时变化和采样边界。新候选需要重新布局、全时序、实际10延时单元/129引脚、CDC及复位范围证明；不得沿用旧`fc1f…`的物理通过结论。板上仍为封存的矫正基线，尚无统计下载或真实FPS。

00:48 后续：delay `build-a` 原生执行67.029秒后在compile失败，源稳定、未超时。错误为top第51行HREF/VSYNC同时接显式INBUF与监测器隐式反相器，PDS报告 `Illegal connection of port`。没有新ADF/位流/下载。`control-delay-sim-a`原厂模型仿真单独通过17.159秒、1024组10位组合/3072检查/32采样边界，报告SHA `d36f8d8d69fb6046c2021678d721cddd0951665b5a64032c52b4b6d8b17c40f2`；该结果只证明原厂模型的名义延时，不掩盖compile失败。

修正接线采用一个显式INBUF的输出分叉：延时前信号给原监测器，延时后信号给采集器。新增独立tap模块、source-b/build-b及tap模型回归，保留已消费A源码/工具/回执原字节；target与短work目录沿用，尚未被真实计划消费的检查适配器将显式绑定新builder。此前原始监测器的物理输入本来也经过INBUF，新的tap接线使这层缓冲明确可见，不增加像素时钟周期、不改变监测极性和周期计数。

01:04 后续：上段tap方案B仍未实现映射。build-b已通过compile/synthesize，但DeviceMap-0020明确拒绝INBUF.O同时连接ZEROHOLDDELAY和其他逻辑，362.172秒exit1、源稳定，无最终ADF。回执SHA `8301594f5b8f6baf4ee5f2d2a067111643f81cc8ef9a482aa6f3ca24f8f4b6a3`。独立tap模型仿真通过12.328秒（报告`f73e55d2ee6c3167732a00f8a0cc3ce68b75b2bcb76628ff827555b452f6d04b`），但它不证明原生IO结构可映射，原件保留。

当前转为C：`source-c/build-c`仍在短目录且同target，IBUF.O只连ZEROHOLDDELAY，延时后的DO同时送采集器和监测器。**这会把监测器所观察的两路控制也延后名义1500ps**，不再声明监测器原始控制输入时点不变；PCLK、监测算法、分辨率、传感器配置、矫正流水线不改。监测器没有数据端口、只按PCLK统计边沿/行/帧，需额外用真实模型验证完整2560字节×720行计数、坏行拒绝和断钟撤销，再做新PnR/IO/时序。新的图合同必须是`MonitorAfterControlDelay`与`AllControlConsumersDelayed`，不能复用B的pre-delay tap接受条件。

01:16 后续：C 已通过 compile、synthesize、device map，实际布局仍进行，尚无完整构建/时序验收。共享10路延时原厂模型仿真12.184秒通过，报告SHA `3e7b1ea7e7b9a01fe4b10b8f6a21eb48ad410510d9486601b88c10bb089475ce`；完整真实frontend/monitor仿真160.160秒通过，报告SHA `459222f14e8e42d43959518a9e2575fb571a1ebe125a0b28e206a571dacd3860`。四场景覆盖42/47.25MHz各自两完整2560字节×720行资格判定、单帧仍禁用、坏行拒绝、停钟粘性故障；这两个频率是保留的寄存器模型场景，并非实测。两份报告输入无漂移，root独立绑定到build-c实际编译源码共63文件。新位流工具现在强制同时绑定共享延时和完整监测仿真；74项现有CPU回归通过，新增负例复核进行中。实际时序、下载及UART读数仍待完成；板上仍为无遥测的矫正基线。

01:21 后续：C全部原生阶段实际完成，740.886秒，native exit0，输入稳定，STA前后ADF一致 `ac00dabf39ad37064560713ba695f16ac1dea3cfa1968d627c515ca83b081356`；原52条缩位诊断保留，ExecutionCompletedWithoutError=false。数据setup slow/fast +0.388/+2.927ns；slow hold全过+0.060ns，fast仍1条−0.022ns（ddrphy_sysclk→phy_dq_sysclk_1，非相机输入）。camera_pclk保持时间双角通过。recovery245/230仍失败；removal/MPW双角全过。已开始export-c实际网表导出，report-c与精确剩余hold发现随后串行执行。原C复位应用必须被剩余hold阻断，不能先加例外掩盖数据失败。当前尚无统计位流生成/下载。

01:30 后续：export-c真实成功124.633秒，hold-discovery-c真实成功132.027秒，reset-query-c真实成功64.896秒，全部输入无漂移、无严重诊断。剩余hold精确为DDR group2 ck_dqs_diff[0]双Q分支至u_outbuft_dm/TX_DATA[1]的单负载终端 `_N112`，不是相机路径；8条实际slow/fast setup/hold覆盖L5Q、L6Q，最小setup+3.755/+5.158ns，hold+0.261/−0.022ns。原line700 MultiCycle Path Setup -end 2完整保留，不新增放宽约束。准备单终端局部绕行，修复后必须新完整STA与功能/布线/例外核验。实际39802cells/18692FF图中10共享输入延时及444统计FF同core无反馈核验通过，暂无最终延时覆盖结论。复位实际5组127对精确名字查询通过，原C应用仍被hold阻断。

01:40 后续：physical-route-c在独立副本实际执行成功，182.284秒，Exit0/InputDrift=[]/Diagnostics=[]；新ADF `5af32515f613033e63fbd41b8137caf3ff91a8e1487587f50bdc21167ab3a221`。只改变 `_N112` 单分支，其他36260路线、功能/放置语义和父对象绑定的CDB定义/条目全部保持。原生保存所做源位置元数据清理已按确切结构核验，不把逐字节差异忽略成任意等价。尚待本候选fresh完整STA，修复保存成功不等于hold已通过。下一阶段先repaired-report-c复测，再repaired-export-c与已核验复位范围应用。

01:47 后续：repaired-report-c真实fresh复测已成功，源ADF5af32515…，数据setup +0.388/+2.927ns、hold +0.060/+0.020ns双角全部0失败；removal +0.310/+0.171ns、MPW +0.035/+0.035ns亦全过。原唯一DDR hold修复关闭。仅先前已精确核对的recovery245/230仍待复位范围处理，不能宣称十表全通过。正在接续repaired-export-c，然后按相同功能图/实际127端点对施加精确复位范围并重做最终检查。

01:55 后续：repaired-export-c真实成功123.476秒，重新导出的当前网表与5af32515…候选一致。repaired-report-c回执SHA `b6a76e875db2510ec5043dc2caa945acfb092c3f0d19cc404929c76c20075a7f`，77.850秒。因同一上游完整解析重复耗时，新增明确source seal及兼容executor：先按冻结原checker完整审计一次，再每次重hash全部源/工具/实际工件；fresh原生时序/网表/布线/功能/复位范围检查仍保留。hold sourceauthority SHA `05793930386c6bfe29ce04c70a210d52a793b18823a082fc4b59f7f18089d7cf`。仅首次消费前的repaired apply/effect增加此明确authority接口，freeze-a保留、freeze-b另存；83tests+29subtests通过，root独立重跑其中41tests也通过。正在真实图/FF/route/nonreset检查后准备repaired-reset-apply-c，不提前写通过。

02:02 后续：repaired-reset-apply-c真实成功，156.010秒，Exit0，结果ADF `29e2e519cdb7e27ca43209dd57761bd8e70d2e761decbfebf96f5167b311e19e`。本次只施加实际5组127端点对的精确复位范围，当前全部数据setup/hold继续计时；实际名字与已核验选择器一致、路线/放置保持检查通过。正在封存完整来源并准备repaired-reset-final-report-c与export-c，尚不能宣称最终十表或CDC全通过；无统计下载/实板FPS。

02:07 后续：repaired-reset-final-report-c实际fresh原生报告与route查询成功；最终ADF29e2e519…双角全部十类时序0失败。slow/fast分别：setup +0.388/+2.927ns，hold +0.060/+0.020ns，recovery +1.445/+3.869ns，removal +0.310/+0.171ns，MPW +0.035/+0.035ns。final sourceauthority SHA `d0e32693f4b7e6cea415e6357d017ed59d049c53b7efd20f57bf1666f0fdc332`。final-export正在实际执行，随后effect审计与最终IO/CDC重新派生并行；仍无统计位流/下载/FPS，不能用十表通过替代完整CDC/外部或实屏验收。
