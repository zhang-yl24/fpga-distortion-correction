# 当前交接点

## FPGA-1028-GIT-AUTHORIZED-RESUME-ONE：已撤销午间暂停；先审查同步main，再恢复离线工程

用户明确授权原私有仓库main逐path审查/暂存/commit/push，不强推、不覆盖远端新提交。初核本地/远端HEAD均feccb488...，暂存区空，未发现本标记既有提交；Git与工程写入串行，未启动新EDA。372项原待审文件无已知secret/受限源码标记，vendor无修改；精确范围及排除理由在本轮审查清单，受限/机器/构建资料留本地。

最新复位两源、FDC/RCF、bench和C独立候选以新文件导出并绑定原SHA，不覆写封存候选。parser/runner仅适配CLI/路径，未借用旧回执宣称新runner已完成EDA；细节见`handoff/离线复现与同步范围-20261028.md`。本节只表示授权和Git准备，commit/push及远端一致以实际回执为准，未提前称同步完成。

同步后只做一个有据最小离线里程碑；不无因重跑已通过八帧/同配置PNR，不宽泛false_path、猜改vendor、降频或放宽约束。recovery每角245未过、C行乘积候选仅单位测试，下一步需独立等价/流控/边界验证后才整合。开发板保持断电，B封存、全部正式放行false，不操作电源/睡眠/唤醒，不生成bit或硬件计划。

## FPGA-1028-IDLE-WINDOW-EXTEND-ONE：12:30延长窗口生效，已确认安全空闲并暂停下一重任务

本更新明确替代IDLE-WINDOW-ONE的11:50过期条件，旧消息迟到不得覆盖。12:08:28北京时间同权限只读核wrapper/全部已知工具后代及候选路径native进程均为空；所有既有调用自然退出，下一C重型RTL/RCF PDS明确暂停，没有新任务启动/kill。已核保存结果、最终ADF、实际加载输入及当前冻结源码/夹具哈希，全部匹配；首个只读核验因相对键/绝对键KeyError退出1，第二次按原清单准确路径核对通过，错误记入新回执，未触发原生工具或改结果。

请协调据此确认15–20分钟测试空档，测试由协调和用户另行发起；本线程不休眠、拔电、设置唤醒或碰板。窗口截至12:30；测试已开始则等协调确认结束/稳定供电再恢复；若12:30未启动测试，本窗口不再要求等待，回到原授权任务但不无因重跑已通过八帧/PDS。不承诺Agent自动唤醒或续跑。

确切恢复顺序、失败/未测、日志及输入SHA见`distortion/build/offline-20261024/resume-parallel-20261028-a/idle-extend-confirmation.json`与所绑定的`safe-pause-final.json`。八帧数字证据及独立C单元证据保留；recovery每角245检查未过、外部IO/CDC/实物与光学仍未接受，B封存及正式false保持。

## FPGA-1028-IDLE-WINDOW-ONE：12:06后消费，已过11:50；本条窗口不触发停机

此为协调消息，不是新工程任务。当前已超过本条11:50判断点，不为12:10窗口杀进程、休眠或等待；已完成的同源native8/PDS不重启、不重跑。12:04:44自有进程全部退出的真实证据保留，本轮仅保存协调状态，无新重型/设备/电源操作；后续工程仍按既有准入条件和真实下一任务推进，不由本窗口重复启动。

官方collaboration.list_agents核A/B/C均completed，未为配置变化触发新回合。用户模型偏好已记录：gpt-6.1-sol，常规high，复杂DDR/RTL流控xhigh，极难架构才另说明更高档理由。当前支持工具没有已有代理的在位改档及配置读回入口，本轮配置未修改，也不将用户给出的此前ultra状态冒称已改。下次真实独立子任务可用spawn的显式model/reasoning_effort参数（覆盖时fork_turns=none）；实际读回前不报告改档成功，不另建原工程执行器。回执`distortion/build/offline-20261024/resume-parallel-20261028-a/idle-window-one-consumed.json`。

## 安全暂停已确认：2026-10-28 12:04，自有工具全部自然退出

本轮只核对既有结果并写本地交接，未启动新八帧/仿真/PDS/STA。既有wrapper session75135已返回0；PNR原生0（553.249s）、已提交的最终ADF STA原生0（36.184s）。12:04:44北京时间同权限只读核验wrapper及已知子进程树、候选路径native进程均为空，没有kill。后续重任务/Git写入暂停，等待用户/协调下一步。没有休眠、唤醒、定时任务或电源/网络/权限修改；06:00来电不保证Agent续跑，开发板继续断电。

A /root/rtl_audit、B /root/evidence_audit、C /root/calibration_audit均已完成，文件范围与启动证据保存在原parallel-start及各自回执。当前两份修订RTL、109源/夹具与B封存保护不变。已完成的新源原生8帧PASS（旧native不冒用）：最坏3816061周期，steady新扫描30.0fps、累计滑移0；它是合成参数/行为DDR数字证据。独立C rowpipe unit PASS（64个连续输出/63间隔周期），尚未集成/全帧/物理验证，不借用主候选结果。

RCF两条原生命令均报successfully，原报告PositivePerNetApplicationProven=false保留，不将命令成功等同复位安全或物理效果改善。新最终ADF SHA 897ef3a8c98a45c0c47a1fad45711ca40c25dd82e584520e9a9007ba3d4d95c0，STA前后相同。slow/fast setup/hold/removal/MPW无失败，recovery仍每角7组245检查（不是相加的独立FF）；主域slow setup+0.116ns仍薄。所有PhysicalTimingReady/HardwareReleaseAllowed/EligibleForPDSOrHardware及四项正式false保持，外部IO/CDC/五个无同域观测时钟域/真实标定与硬件仍未验。

完整暂停回执：`distortion/build/offline-20261024/resume-parallel-20261028-a/safe-pause-final.json`；本次结果汇总`result.json` SHA 9cfd3c16f05b645520684412dc40593b2f85c1d6fb5449495f2086e0b91c2178。原夜间23:50前收尾与预检命令仍在`ddr-reset-parallel-20261027-a/power-window-handoff.json`，不回写历史；中断无帧级续跑，不把部分帧算通过。最新12:30前休眠/来电重连测试仅由协调确认、用户实际操作，本线程保持空闲。后续先确认稳定供电/时间窗及冻结SHA；不因恢复而重复已通过同源八帧或RCF PNR。

## FPGA-1028-STEER-SAFE-PAUSE-ONE：接受最新12:30测试窗口；当前PDS自然结束后暂停下一重任务

最新引导已立即消费，不等工程大回合收尾。11:59核实wrapper41532/PDS50436/PNR子30688仍正常布线；当前已提交wrapper自动包含最终ADF STA且无安全阶段暂停hook，允许这一完整调用自然完成，不杀父/子进程、不改冻结helper。随后不启动任何新独立PNR/STA/仿真或Git写入，只保存日志、真实退出码、前后hash及恢复交接。不能仅以interrupted/单条命令返回宣称全进程退出，必须同权限只读核wrapper及所属进程树。具体状态在`distortion/build/offline-20261024/resume-parallel-20261028-a/steer-safe-pause.json`，空闲尚未确认。

用户12:30前可配合15–20分钟休眠/来电唤醒重连测试；需父协调确认后由用户操作。本线程不休眠/拔电、不改电源/唤醒/网络/权限，不自建定时任务。旧11:50窗口由本引导取代，不删除其他用户消息。开发板继续断电、B封存，全部正式放行false；本轮未开始Git写入。

## FPGA-1028-RESUME-PARALLEL-ONE：AC在线恢复，唯一新源原生八帧运行中；A/C隔离准备

用户10/28明确恢复离线多任务。root实际Windows PowerStatus确认AC Online/95–96% charging，无冲突RTL/PDS；新入口显式重新冻结，昨夜PREP_ONLY及拒绝记录不改。原ADF c65db9...fec88、result9eeaab...125c及两RTL/FDC SHA匹配。root唯一重型回归已启动，目录`distortion/build/offline-20261024/board1080-cdc-reset-20261027-a/native8-resume-20261028-a`；compile/elaborate原生0，simulate运行中，尚未八帧通过。7200秒/80M周期总预算，自有清理另最多30秒；每2秒供电/阶段记录，AC离线或未知则停止自有进程并保留部分证据，不支持帧级续跑。`resume-parallel-20261028-a/root-native8-start.json`保存精确命令/冻结入口/预检；`root-native8-observations.jsonl`补实际events.csv进度，最终只以完整源绑定回执验收。

A `/root/rtl_audit`仅`resume-parallel-20261028-a/a-rcf/*`：真实官方指南证明dev_map后可add_constraint RCF，独立fullflow只新增此行，9项静态检查通过但未EDA。新增复位边界：SynVM两级FF在最终PNR映射为gopSRL2，物理级间/CDC语义未证，245 recovery不豁免。B `/root/evidence_audit`仅新b-*准备并审核入口、主线程执行；C `/root/calibration_audit`仅c-decode/*独立弹性行乘积RTL/bench，未改主回归源，待重型令牌空闲后由root串行定向RTL。主线全源/夹具冻结，PDS须等原生回归/必要修复验证完成再评估一次独立诊断。当前无板卡/串口/JTAG/GUI/下载/Flash/bit/硬件计划，所有正式门禁false保持。

## FPGA-1027-POWER-WINDOW-ONE：23:50前安全收尾；今晚禁止长跑，等待后续

供电已明确：00:00–06:00断电、电脑需休眠；本线程不创建唤醒/定时任务，不修改电源/休眠/网络/权限，不立即休眠电脑。06:00来电不保证唤醒或Agent续跑。23:45:16已完成上一保存点；本次只追加供电与恢复交接，A/B/C均已完成，无运行中的RTL/PDS，不启动本晚原生八帧。

恢复顺序：用户/父协调先确认电脑确实唤醒且稳定供电；在`D:/English/FPGA`运行现有B入口仅preflight，核当前源与small gate；root另行审核并冻结可执行入口后，才新建`board1080-cdc-reset-20261027-a/native8-post-reset-a`并执行唯一原生八帧，7200秒/80M周期上限。当前`--execute-sim`仍严格拒绝，不能直接开跑。中断不支持帧级恢复，须保留部分日志并重新完整运行；部分帧不通过。确切命令/目录/哈希/状态见`distortion/build/offline-20261024/ddr-reset-parallel-20261027-a/power-window-handoff.json`。开发板继续断电，所有正式false保持；等待父协调/用户下一步。

## FPGA-1027-DDR-RESET-PARALLEL-ONE：三路轻量并行完成，发现RCF缺口；确认午夜断电，今晚不长仿真

无冲突工程运行，root唯一执行者；A `/root/rtl_audit`只写a-DDR证据、B `/root/evidence_audit`只写b-native8准备、C `/root/calibration_audit`只写c-地址译码方案，启动/文件所有权有记录。用户明确00:00–06:00仍断电，今晚不启动长仿真；不改电源/睡眠/计划任务，不承诺06:00自动恢复。本轮RTL/PDS/设备访问0，冻结109源、派生FDC、B bit/回执不变，全部正式false保持。

A查到当前71份加密RTL与安装包HMIC V1.10逐字节一致；官方生成器要求BANK_NUM2的两条IOCLK gate优先路由RCF，现候选route-widget无输入且未见原生日志加载。root仅生成独立未加载RCF提案，9项静态检查及最终PNR.netlist的exact2目标匹配通过；它不是复位例外，不能称245 recovery改善。入口首级及244 PHY reset/training的精确豁免/安全依据仍blocked，11时钟/6有同域/5无同域观测完整保留。A最初漏8个nested时钟的派生报告原件已存档并修正，不改原生数据。

B已准备当前新System同源的原生1080八帧入口，109板级源/33仿真源/33夹具参考输入冻结，预检与12项CPU拒绝测试通过。默认仅preflight，真实执行明确拒绝，未创建native目录；新版本原生八帧仍未测，旧native-a不覆盖。后续稳定供电需用户明确确认，再由root审核/冻结执行入口并创建一个fresh运行目录，7200s/80M周期上限；中断后只可重新跑完整八帧，无帧级续跑。C只提出一层elastic row-product地址译码方案，root补1572864组数值检查，未改RTL，也未验证流控/吞吐/新STA；当前+.191ns仍是窄裕量。

总回执`distortion/build/offline-20261024/ddr-reset-parallel-20261027-a/result.json` SHA 506ae68ab587204ce6092af49a0bc1222ef1c82bb1a03eef8cd7d545ef81d002。下一步为稳定供电后一次新源native8；独立审核RCF绑定及DDR端点协议，不在本轮再PDS/上板。

## FPGA-1031-CDC-RESET-ONE：702个setup失败已消除，DDR recovery仍未过；继续断电

仅在`distortion/build/offline-20261024/board1080-cdc-reset-20261027-a`派生两份RTL：top用sticky power_ready寄存启动释放；System的bank_core/reader/read_bus改接已有core本域cr。多域FIFO/输入/扫描仍保留共同断言及各域释放，厂商IP、时钟、FDC/8ns限制均未改。24相位（含edge±1ps）/旧FIFO epoch/停core启动释放、独立时钟7项启动与6类sticky/held-AW控制、32×16实际DMA→SCATTER4→FIFO→8帧像素CRC/故障隔离/银行复用/排空均PASS。旧原生1080八帧未重跑，仍只证明旧源版本。

唯一真实compile/synth/map/PNR各执行一次，原生/CLI均0，729.328s/4500s；显式新最终ADF STA原生/CLI0，54.233s/900s。新ADF SHA **c65db9aa39a5a7320f0b43d08f7cd8d2c0c7a335e5cf1b4c7e3a5fbfb67fec88**；原E ADF dbbdae...2537原样保留，二者均不是prr索引哈希。slow/fast setup、hold、removal、MPW全部无失败；slow recovery382→245（7组），fast245→245（7组）。仍为244个DDR内部TSR/RST/RST_TRAINING_N检查端点及1个board27→rst同步器首级端点；后者−9.557→−3.795ns，Timed(unsafe)仍在。不同角/类型不合计成唯一FF数，完整内部时序未接受。

核心slow setup+0.047→+0.191ns，仍不算稳健；当前worst改为queue_y[1][8]→pixel_number[0][28]/D，8级逻辑、布线4.520ns/61.7%，若另做余量优化应聚焦该地址译码局部路径，不能沿用旧tag/CE瓶颈。最终LUT16785、FF19192、DRM17.5、APM79、IO134/pad差异0；实际cache8×36K双口/FIFO各4×36K/3×18K保持。11时钟/6有同域数据/5无同域路径、2不可展开、IO缺delay54/110、53共享引脚（DDR15/其余38）与63个async_reg ignored均未豁免；外部DDR/HDMI AC、BASE V1.4/skew、CDC及Gray skew未签核。

总结果`distortion/build/offline-20261024/board1080-cdc-reset-20261027-a/result.json` SHA 9eeaabe85002e0d9dfdd125ee5491031042ba650d02e85cea2c7a23e212d125c；`final-strict-timing-audit.json`保留所有原生类型/unsafe/缺项，15项严格schema/−0.000失败计数/ADF绑定测试PASS。首轮沙箱GCC启动/elab失败和首个PDS相对路径加载失败均保留；后者发生在编译/PNR前，未产生旧源误测。原109源、138旧保护文件、B bit/回执不变；无新bit/硬件计划/设备访问，所有本轮调用已结束，所有正式false保持。下一步只针对DDR复位同步器及PHY训练端点核协议/精确约束依据，禁止全域false_path或无依据改IP；本轮不再PDS，不自动接板。

## FPGA-1031-BOARD1080-DIAGNOSTIC-ONE：真实板级资源适配，已完成最终DB诊断STA；内部跨域/复位未过，继续断电

新增独立diagnostic-a至e，原109源/RTL/FDC、138旧保护文件和B位流/回执均无漂移，native-a不重跑。真实board1080_top、DDR/PLL/官方MS72xx闭包compile/synthesize/dev_map完成；31个角色正确的add_design展开104个唯一HDL正文，无测试桩或未知/空DDR/PLL黑盒。E实际SynVM确认cache为8×36K TRUE_DUAL_PORT，display/capture各4×36K，tags及两份初始化ROM合计3×18K。最终PNR资源：LUT16859/66600（25.31%）、FF19192/133200（14.41%）、DRM17.5/155（11.29%）、APM79/240（32.92%），134个实际引脚与参考pad全匹配；608分布式RAM已含于LUT。

最终原生PNR exit0、完整project wall714.210s/4500s，工具实耗PNR422s；project-run实际重复前端一次，不能用原runner的FrontendRecompiled=false。原runner因只认另一种成功标记而CLI1/Completed=false，原回执保留，独立原生日志+新DB检查与9项host分类回归确认PNR完成。a/b Tcl入口失败、c漏物理PCF导致DDR放置失败、d仅PNR工程图缺dev_map前驱均保留；共3次真实前端、2次实际放置尝试、1份成功routed DB，不隐去失败或重编成本。

冻结最终DB SHA dbbdae506307572c718d8167a78c2f206c78feb5f95e0873dbff628130752537；显式从该DB运行STA exit0/CLI0，51.416s/900s，DB未变。解析11时钟、6同域slow/fast setup/hold非负，共59595个slow-setup端点；125MHz核心slow setup仅+0.047ns。**完整内部时序未过：slow setup 702失败/−1.450ns；slow recovery 9组382失败/−9.557ns；fast recovery 7组245失败/−6.074ns。** interaction的board27→core 729=702 setup+27 recovery，并非豁免；不同检查/角的数不能当唯一寄存器数相加。主问题为启动复位/使能分布及DDR PHY复位释放，不能加宽泛false_path掩盖。66个async_reg被工具忽略，CDC协议/skew未签核。

诊断FDC移除4条无依据IO delay，其余真实时钟/DDR generated clocks/uncertainty/原例外保留，派生候选恢复原参考73项DDR电气属性并正确携带PCF。no_clock=0，no_input_delay=54/no_output_delay=110、2组周期不可展开；全部外部IO未签核，BASE V1.4与本地PCB V1.2差异、RX/TX AC/边沿/skew仍缺。PhysicalTimingReady、EligibleForPDSOrHardware及四项正式false全保持；无新bit/硬件计划/设备访问/GUI。全部本轮工具已返回，继续断电。

总回执：`distortion/build/offline-20261024/board1080-diagnostic-20261027-e/diagnostic-final-result.json` SHA b1141127dfcaa84f2d2d36e33f965c19ac667dbead86ccd05604662d582772fa。同目录`sta-recovery-cdc-audit.json`含完整分域/恢复检查，`work/place_route/run.log`、`work-sta/report_timing/board1080_top.rtr`为原生日志。下一项是独立派生候选的复位/CDC拓扑审查和最小修复，补必要定向回归后再评估物理重检；先不压资源、不重跑旧native-a，不自动硬件。

## FPGA-1031-BOARD1080-INTEGRATION-ONE：8帧原生真实像素扫描数字门禁PASS；AC阻断未PDS，继续断电

独立新增`distortion/board/board1080_top.v`/源清单/FDC，官方ms72xx_ctl、真实DDR IP用户口、SCATTER4、reader、旧异步FIFO与实际DE/RGB扫描已接入。109源当前SHA全部匹配；142个声明参考pad只是静态数量，8个RGB888输入LSB可被RGB565转换修剪，不能当已测routed引脚数。输入/输出数字目标均74.25MHz、2200×1125、1920×1080/30Hz；60Hz/148.5MHz新PLL不在本候选，当前TX初始化的物理模式/边沿/格式也未接受。

唯一native-a完整8帧已PASS：输入不等core/ready、源DDR由实际DMA/CDC写入（无预载）、非零synthetic Brown径向/切向+插值/GM0、实际读写仲裁/真实异步FIFO/DE-RGB逐像素mask及CRC。每帧2073600pixel/4147200B/129600beat，各路径8帧1036800beat=33177600B、实际扫描16588800pixel；源bank0/1、结果2/3反复新epoch通过。8输入/commit/处理/发布/独立新扫描均8，drop/overflow/no_free/repeat/underflow/CRC mismatch全0，完整所有权/FIFO/仲裁排空。CRC依次D902B095/DCB3BB32/DDBB33B3/D902B095/DCB3BB32/DDBB33B3/D902B095/DCB3BB32。

commit→source_release为3802919/3815511/3815367/3815232/3816061/3814534/3815647/3812543周期，最坏3816061，低于4166666.667目标8.414536%。预声明warmup1–2/steady3–6/tail7–8；steady每帧实际扫描时均接受129584个后续capture W周期。steady发布间隔33.332256/33.339960/33.321120ms（有限发布率30.001999fps、18.84us抖动）；实际新扫描间隔33.333333333/333/334ms（30.000fps、1ps量化抖动、100ms窗口末累计滑移0）。同像素输入→扫描约66.666601ms，首输入pixel→整帧扫描完98.662817ms，仅模型端到端。尾帧不作最坏稳态；LongTermSteadyStateProven/Physical1080p30Accepted均false。

总模型41651765个125MHz上升沿（t=0至全部排空+40guard，含启动/填充/尾部），wall4411.019s<7200/80M上限。读/写双client争用2258/994，AR/AW/W停顿114710/100352/400446，cache/core/tone停顿1188510/1273883/1328291全部非零；native强制等待0。输入FIFO报告峰值1word、输出wr域占用峰值512/512、cache128line=32KiB逻辑容量；不是物理RAM推断。每帧25944fill/830208scatter，重叠停顿不可相加。

本轮7次串行RTL/21条native全0；CLI为0/1/1/0/0/0/0。scan9组PASS；small-a正常8帧后TB phase/reset调度race失败，small-b功能/故障/reset通过但两争用0严格拒绝，原失败及精确历史源码均保留。small-c加仅SMALL的有界强制争用，并通过midframe坏front、释放pulse发出后故障到达的消费沿否决及共同reset。仅新System补消费侧!failed；原bankcore/B不动。输入status单元两极性/坏1919行/停PCLK/复位重准入PASS（83s）；真实boardtop控制body在明确IP/System桩下，7缺资格/6种A1–A6黏住/保持AW接线/共同reset PASS（20s），不验证实际IP/PLL/IIC/数据通路。另一次缺目录预检在RTL前拒绝，已记入总回执。

PDS/综合启动0次：RX tCO(min/max)/选定更新边沿、TX setup-hold/选定采样边沿与板级/转发时钟skew缺准确依据，FDC I/O延迟明确provisional、PhysicalTimingReady=false。当前75.1MHz输入STA包络覆盖数字75MHz上限，输出仍74.25，不能替代AC证据。未生成新bit/最终DB/最终STA/物理DRM-LUT资源；实际DDR IP body未仿真，native使用UI行为模型。netlist/RAM/route/STA是未来诊断输出，不倒置为已存在证明；真实源/PHY/校准/画质/外部延迟/长稳仍未验。

总回执`distortion/build/offline-20261024/board1080-integration-20261027-a/result.json` SHA ac5d8d70dc75228dbd5f725a88b58b7917fbde970372c979ea0ace0dcf366cab，绑定原生命令/退出码、源码/模型/日志/结果、74日志/17结果/68fixture校验及16新源码原字节档。138旧保护文件+原B bit SHA全匹配，零漂移；旧B/INDEX5/7/SCATTER4/私参/helper/bit/失败不改。四false保持。所有本轮已发起调用自然返回、无超时/清理错误，无设备/UART/JTAG/下载/Flash/上电/权限设置或硬件计划。继续断电；无主机失联看门狗，关串口/auto-off不停止视频，停core_clk下故障CDC/排空不保证。下一阻碍是补厂家AC/边沿及skew合同，达门槛后再评估已获条件许可的一次fresh板级PDS；22:30不会自动接板。

## FPGA-1031-INPUT1080-CONTINUOUS-ONE：三帧原生像素流功能及逐帧预算通过，稳态30未接受；继续断电

唯一完整native回归已自然完成：精确74.25MHz、2200×1125、X192/Y41连续30fps数字输入三帧，源DDR由真实DMA/CDC写入、处理核非代理；SCATTER4非零Brown径向/切向+插值/GM0、实际读写arbiter与完整DDR读回逐像素/mask/CRC通过。每帧2073600像素/4147200B/129600beat，各路径三帧388800beat=12441600B；源bank0→1→0/结果2→3→2新epoch和先release/unlock再复用通过。输入/接收/处理/读回均3，drop/overflow/no_free=0，CRC D902B095/DCB3BB32/DDBB33B3；第三源每pixel异于第一防stale。

commit→source_release为3801923/3813676/3811050周期，含持续采集写/显示读回竞争，均低于4166666.667预算，最坏新测余量8.471776%。首有效输入pixel→DDR读回完成模型延迟67.087209/67.086340/66.989542ms。必须分开：发布间隔33.427360/33.312320ms，全3发布窗口29.967180fps；读回间隔33.332464/33.236536ms，全3读回窗口30.044014fps。尾帧读回没有frame4负载更快，不能拿读回率替代稳态新结果率；LongTermSteady30fpsAccepted=false、Physical1080p30Accepted=false。输入30fps三帧无drop+逐帧预算通过不等于持续/物理30验收。

native读/写双客户端争用3433/278，physical AR/AW/W停顿43352/38900/148222，commit stall0（保持已由small21验证）；input同拍/延后首W8678/15622、result8103/16197，全部必需压力非零硬门禁，native forced等待0，最终FIFO/R/W/arb/owner排空。每帧25944fill、830208scatter仍为主要已计数成本；坐标背压与fill/writer重叠，不相加。native一次，wall1472.797s<1800、总16859267系统周期<80M；未改时钟/精度/容量或搜参数。small首轮read_contention0严格拒绝，源码/失败/三行CSV保留；只补SMALL已选AR强制争用后small-b通过。共3次RTL调用/9native均0（xsim fatal也返回0，已独立查fatal），CLI真实1/0/0；8项CPU单测通过。

汇总`distortion/build/offline-20261024/continuous-input1080-20261027-a/result.json` SHA6a2c36b2f3782f473fddb128ac2eece29218516c6e580f32326d80e7743e0ec5；完整源码/模型/fixture/命令/结果绑定、全ps时戳frames.csv/events.csv和独立复核均在同目录。原B/INDEX5/7/SCATTER4/小链及所有失败/四false保留；旧bad-frame/overflow/no-grant/reset、cache RID/RLAST等记录仅核原RTL匹配复用，未重复全套。

本轮结束，无超时/清理错误，所有已发起调用均已返回。开发板继续断电，无UART/JTAG/设备访问/下载/Flash/采集/上电、PDS/综合、权限/安全修改或硬件计划。MS7200真实源/协商/格式/极性、物理CDC/双口RAM/资源/最终STA、HDMI像素显示完成及成功后fault释放语义、真实镜头1080 K/D/光学/外部延迟/长稳仍未验。现场信息未知未阻塞这轮离板回归；下一关口为像素显示/板级top与时序约束及稳态证据，达到条件后再评估单构建，不自动PDS或接板。17:30不触发任何硬件，22:30返回也须另行授权。

## FPGA-1031-PARALLEL-PLAN：DMA/CDC与实际核心小链通过，周六验收关口已更新；继续断电

用户以2026-10-31周六为冲刺验收目标，之后优化展示；非官方截止/获奖承诺。SCATTER4完整结果保留且复用，未中断或重跑。启动实测16逻辑CPU/32GB内存、可用15.24GB、无昂贵运行；最多一个RTL仿真，代码/轻量Python并行，不综合/PDS/设备访问，不生成硬件授权。

真实任务：A `/root/rtl_audit`核原证据/公共接口并新增实际core小链bench/runner；B `/root/evidence_audit`只写独立输入DMA/CDC及其小bench/runner；C `/root/calibration_audit`只写证据工具/15项单测与1031验收清单；root唯一拥有新write link/代理bench、公共接口和CURRENT/计划。详细范围和启动/追加分派证据见`distortion/build/offline-20261024/parallel-1031-20261027-a/parallel-start.json`、`dispatch-update.json`。

B最终small-b已PASS：RGB888→RGB565、同步读FIFO CDC、4B×8拍CRC、完整帧才commit、银行预约/匹配release、几何坏帧/overflow整帧drop和复位恢复。首版只测延后W的small-a保留；审查发现AW握手同拍首W遗漏，已修且small-b实测同拍7/延后6，3条native0。root真实shared-write link+core代理小测一次PASS：AWstall53/Wstall476/两owner争用12/commitstall62/同拍input4+result128，2源帧CRC与release排空。C最终15PASS/exit0；合成CLI预期exit1，真实验收仍UNMEASURED，四false不变。A实际DMA→SCATTER4核心→DDR完整读回两帧32×16已通过：源/结果/读回各64beat，CRC C4631B6C/4F224D3F及mask一致，所有银行排空。首normal case真实双写同时请求为0，原记录保留；仅补一次强制争用case后write_contention=1硬门禁通过，AW/W停顿78/24、commit等待21、display AR等待15。两压力小case不比较性能。它含实际矫正核心但仅DDR显示读回，不含HDMI像素输出。

本轮合计5次串行小RTL调用/15条native全0；C两轮14/15PASS（最终15项），合成CLI两次预期exit1。无新测试失败；审查发现的首W协议缺口已修，旧证据/源码快照均保留。汇总`distortion/build/offline-20261024/parallel-1031-20261027-a/result.json` SHA e196a3927c507e7749670c825507f78efde6f64cda49e560e700ec4e6a6760ba，绑定各源码/模型/fixture/原始命令/日志及分工。全部运行自然结束，收尾仿真/PDS进程0。

关键路径：原生1080p30来源→输入DMA/CDC/银行→带采集写竞争的核心与显示→物理RAM/STA/引脚→同模式正式标定/画质/外部端到端延迟/唯一新帧率/长稳。预载SCATTER4的8.6%数字余量未包含采集写竞争。MS7200只是接收通道，真实原生1080鱼眼源尚未确认；不能用PC转HDMI默认官方认可。参考28个HDMI输入pad与旧B130pad无冲突，但新板级top/像素时钟/Gray约束未就绪，暂不建议昂贵构建。

日期关口和最小现场窗口见`distortion/output/project/1031并行推进与接口.md`与`1031验收证据清单.md`。今天约17:30后建议仅5–10分钟断电确认输入源/线材；之后单独硬件审核通过才另约标定与测评窗口，本轮不触碰设备。自动回正/IMU/双目/60fps/展示特效后置。所有旧B/INDEX5/7/SCATTER4/失败/四false保留；主机失联或停钟看门狗未新增。当前不自动上电、下载或运行任何硬件计划。

## FPGA-1027-SCATTER4-OFFLINE：32KiB下两帧数字周期预算通过；保持断电并等待

仅新增独立experimental scatter4缓存及必要类型连接、定向/full bench与runner；原B/INDEX5/7/私参/约束/bit和原失败保留。唯一性能改动为even/odd RAM各复用双口，fill散写64→32周期；另抑制复位期间RAM访问。容量32KiB不变，同非零Brown synthetic/development golden、0°/GM0、精度、125MHz目标和六段原压力激励/8份fixture哈希一致。

完整1920×1080两帧exact像素/mask/CRC通过，D902B095/DCB3BB32不变；每帧2073600像素/4147200B/129600写入及完整读回beat。commit接受→source_release总周期为3795064/3807719，原同口径4623361/4634405，节省828297/826686（17.915%/17.838%）。两帧加显示读回/最终排空7795396，原9450382。每帧25944fill不变，scatter830208（原1660416）；最坏低于4166666.667目标358947.667周期。只是数字预算通过，不能称实板1080p30。

本轮3次串行RTL调用、9条原生命令全0/无新失败：首定向→一次完整两帧→补强定向。末写复位/末scatter同bank切帧/新epoch失效/128像素重排/FIFO2排空/RID-RLAST错误隔离通过；显式miss-empty与读写互斥。每帧物理AR/AW/W/cache/core/Gamma输出停顿均非零硬门禁，完整读写/仲裁/owner排空通过。全部仿真自然结束，收尾相关仿真/PDS进程0；未重复旧全套或基线。

总结果`distortion/build/offline-20261024/scatter4-20261027-a/result.json` SHA a98d282966a4cb997a44f393b632c7a5b5c4dca3359d031726bb3f5d5335c4b2；真实CLI/原生argv/exit、CSV/运行日志及完整source/model绑定在同目录。短交接`distortion/output/project/SCATTER4离板结果-20261027.md`。新cache SHA db3c8f924f22d6a67d80d3e7a9e10ec8dba39d6ae30d12637ab5aa06d6005d2b。

**本里程碑已完成并等待下一条。** 四false保持；不综合/PDS、不COM/JTAG/下载/采图/Flash/上电，无新硬件计划或授权。双口实际推断/物理DRM-LUT/最终STA未测，不能借用B资源；输入仍DDR预载，inputDMA/异步HDMI未集成，真实镜头1080 K/D及实板性能未验。display成功后故障语义仍未覆盖/sticky display_valid限制保留。下一真正阻塞为独立候选物理推断/125MHz时序及原生输入DMA/CDC，本轮不再搜索缓存。开发板继续断电，17:30不自动恢复。

## FPGA-1027-1080-CORE-OFFLINE：原生0°数字功能通过，30fps周期未达；本轮完成并保持断电

仅离板新增experimental模块/bench，原B RTL/私参/约束/bit及原失败记录保留；无COM/JTAG/下载/采图/Flash/PDS或硬件授权。固定0°，不把IMU/自动回正/双目/大角tile作为核心前置。新增非零Brown合成模型，真实新镜头1080K/D未接受，四个false不变。

原生1920×1080两种纹理，每帧2073600像素/4147200B/129600beat，映射/缓存/双线性/Gamma0/DDR线性写回和完整读回exact像素/mask/CRC通过（D902B095、DCB3BB32）。独立4MiB银行按0x100000个4B单位实现，四bank16MiB，验证边界/所有权、held commit/grant/数据反压、帧切换排空及源不变。source在bench预加载，未集成真实输入DMA。独立显示17bit计数129600请求/全像素CRC及小帧/坏CRC/断供四案例通过，未连成真实HDMI顶层。

基线6986824/7000559周期。唯一性能优化仅新engine INDEX5→7（逻辑cache8→32KiB），同模型/精度/125MHz目标/DDR背压，降至4623361/4634405周期，约省33.8%，但最坏仍超4166667目标11.23%。两帧含完整DDR读回排空总周期14179988→9450382；不是实板FPS/端到端延迟。INDEX7每帧25944次fill、1660416scatter周期，残余9744reload，当前真正数字瓶颈是cache fill/scatter与邻居慢路径，不能归为板容量差或未做选做项。不再追加优化。

9项golden单测PASS；6次串行RTL调用含3小冒烟、两完整帧套（基线/唯一优化）、显示四案例。首小冒烟bench误判旧front刷新而fatal，原失败保留；修正及offer锁覆盖后通过。后3完整套compile/elab/sim均原生0/functionalPASS。每次有周期/墙钟预算，无并发昂贵构建，无旧全套/PDS重跑。

总结果`distortion/build/offline-20261024/1080-core-20261027-a/result.json` SHA f221aad40a07ad758f232d92cb1470aa2133756642da442ab77f197104dc7fdd，绑定源码/模型/真实命令/结果；细节见`distortion/output/project/1080核心离板结果-20261027.md`与各cycles.csv、display-result.json。Selected原B六文件、manifest/bit离板SHA核验未变；新候选物理资源/STA/引脚/bit均未做。

**本里程碑完成，等待下一条；开发板继续保持断电，17:30不自动接板。** 下一数字步骤只针对0°cache填充串行成本，以同golden复核；MS7200实际源/接收/capture-DMA/CDC仍未集成，未声称电脑相机转HDMI获答疑认可。硬件短测仍须单独恢复预算/现场审核和新授权，不复用已耗用计划。

## FPGA-1027-RECOVERY-OFFLINE：最小恢复预算修复及132项合并回归完成；继续断电等待硬件审核

硬件授权已耗用。本轮完全离板：不COM/JTAG扫描、不访问板卡、不下载/Flash/重试、不PDS/整体RTL仿真，不生成新的真实可执行硬件计划或授权；不修改已封存RTL/私参/约束/bit。SRAM-ONE原20份保护文件和passed=false全部SHA不变。

仅改gamma_pipeline_session和program_idle_heartbeat及相关tests。恢复不再硬传30；候选和恢复分别封存client预算，默认各90/上限120秒；按当前3791112B/1MHz整文件估算30.328896秒，加20秒shell余量×1.5→最低76秒。预算是基于已测Program30.9/日志输出窗口约42.793秒的保守工程门槛，不是严格sbit物理下界。显式合格值保留，不等/缺失/过小/非finite/失配值在候选前拒；旧计划不迁移。UART仍12–30秒。scan/program分别使用client预算，整段不能称只90秒。

计入两个server启动、两个client、四owned的5+5秒清理后，每段已知等待项240秒；候选240+UART30+恢复240+host余量30=最低外层等待540秒，默认600/最大900，显式不足预检拒绝。outer_wait是封存等待合同，CLI没有新增外层kill或失联看门狗；外部runner仍须单独审核，不能保证主机被杀/死机后finally运行。finally恢复仍独立idle检查，不受候选receipt/source错误阻挡。

共享idle.prepare_plan要求调用方显式预算；新版Gamma/heartbeat CLI传90。未迁移的旧raw/pose/capture入口会在准备阶段拒绝，避免原30/60硬值在候选已上板后才冲突。本轮不扩展修改旧采集分支。

相关合并测试2轮：128PASS/exit0，补4项后最终132PASS/exit0，共260case执行，零失败/错误/skip。虚拟43秒program成功、真实Python假子进程超时与只清owned、native0但缺新DONE拒绝、预算/receipt/磁盘失配与CLI覆盖前置拒绝、UART超时后完整恢复均覆盖。无真实PDS/端口调用。

B123源/native0/125MHz最终STA/130pins/私参/bit/manifest保持；新host SHA b9cd9aa906527d95b4f1650b29096368a3faa0f4f877859e924fe300c8c8527f，新idle SHA fd1c78e97102c4771b97304cd94659f95fc6ffdc20711ee21ece4d6bedaf8a07。历史B freeze/D overlay不改，新关系见`distortion/build/offline-20261024/fpga-1027-recovery-offline-helper-overlay.json`；命令、A/B XML及纯预算说明同目录。详见`distortion/output/project/恢复预算修复与离板回归-20261027.md`。

**里程碑完成，仅离板并等待后续单独硬件审核。四项false不变；新预算尚未实板验证，原恢复失败不改成功。没有新真实计划，不能复用SRAM-ONE已用计划。**

## FPGA-1027-SRAM-ONE：候选零角开发通过，但heartbeat恢复超时；整轮失败并保持断电

用户授权一次指定计划，已执行且不能复用：`distortion/build/offline-20261024/gamma-pipeline-session-20261027T041235967878Z-4efcb772/plan.json`。执行前冲突0，实际COM5/CP210x VID10C4 PID EA60 serial0001，JTAG PG2L100H/0x00602899；所有文件/未用/固定恢复绑定门禁通过。唯一一次1MHz/0°/115200/SRAM；无Flash/采图/1080、无测试或PDS重跑，未改候选/helper/四个false。

候选cfg_program成功并有本次postscan DONE=1，candidate receipt passed=true。UART实际10.7786秒，11/11健康样本，0°ACK/结果/保持/最终auto-off ACK均通过，错误计数0；2.05927秒同相位窗口新增CF47≈22.824/s，PF124≈60.216刷新/s（包含重复），内部ADC近似42.33–43.91℃。CY719766–724265不是端到端延迟。仅GM0、零角和有限遥测，不是画质/正式标定/长期稳定或1080验收。

**固定heartbeat恢复失败**：programming_attempted=true、passed=false、done_confirmed=false，program client30秒超时，日志停在cfg_program，无本次编程后新scan。原候选1MHz原生日志Program已用30.9秒，且候选/heartbeat位流同为3791112B，恢复30秒整个client预算不足；这是先前计划审查遗漏，不修改旧receipt洗成成功。整轮result passed=false、CLI真实exit1、总110.790秒。没有重试或重建计划。

已立即要求关外接电源；用户一度断电后重新插上，随后最终明确“已关闭并保持断电”。CLI退出、串口关闭路径无报错，双方cleanup_errors=[]，OS后核对PDS/JTAG进程0。后核123源/9helper/计划/bit不变。没有新heartbeat成功事件，最后历史成功回执不能当当前状态。**从现在起仅离板，不得再访问板卡/串口、下载或采集，等待新指令和恢复预算审核。**

原始result、候选receipt、失败恢复receipt、UART与进度在同session；独立`sram-one-final-audit.json` SHA732d1662f043fb7d22128793eea698727fb1052bfed745b9400a620d64c68ede。详见`distortion/output/project/DA07零角短测与恢复超时-20261027.md`；限制`sram-one-hardware-hold.json`。下一项仅离板修正恢复时间预算并定向检查/单独审核，不改或复用当前已用计划。本次里程碑结束等待。

## FPGA-1027-D：1080输入与吞吐路线核定、主机恢复前置修复完成；仅离板等待

用户本轮现场确认：当前仍为采样OV5640模组，CAM2的40针方向和FPC锁扣未变、未调焦；外接电源正常、无异常发热，本人在场可立即断电。这是操作员确认，不等于本轮已扫描器件/COM、测电压或温度。D未访问板卡/串口、未下载/采图/Flash，未改安全或计费设置。

1080决策已用本地OVT原手册、板卡/DDR/MS7200资料和官方Linux v6.6源码核对。现8bit单沿RGB565/YUV422有效数据就需124.416MHz，超过parallel PCLK96MHz，否决此配置；RAW8有效62.208MHz、示例含消隐84MHz仅输入有条件可行，须新采集/CFA/去马赛克/ISP与同模式标定。参考40针有MIPI复用网，但替换模组/差分路径/DPHY未验，不能声称可用。最短原生1080系统输入候选为板载MS7200 HDMI，无采购假设；不得把HDMI输出放大VGA算1080处理。

DDR为资料中的2×4Gbit共1GiB/x32，IP1000MT/s、UI125MHz×256bit给4GB/s共享理想峰值，持续效率未知。1080 RGB565单帧4147200B，现1MiB银行不能直接用；沿2的幂布局需4MiB/银行、四bank16MiB。125MHz/30fps只有2.00939周期/像素；现tile writer至少3N=6220800周期/49.7664ms，已超33.333ms，且显示requested_words16bit不足129600beats，须至少17bit；缓存每fill另有SCATTER64拍和256B流量。输入可行不等于整链30fps。完整表、路线与最短里程碑见`distortion/output/project/1080p30输入路线与吞吐核定-20261027.md`和`fpga-1027-d-budget.json`。

只修主机关键问题：gamma_pipeline_session新增独立check_idle_plan，在候选动作前和恢复前拒绝旧receipt、非fresh状态、磁盘/内存plan不符、非独立直属目录、频率/PDS/固定heartbeat及脚本绑定不符。finally独立检查idle，不因候选receipt或候选源码检查失败阻断固定恢复。最终一次合并生命周期定向回归55PASS/exit0，无失败/错误/skip，全部模拟设备；未重跑整体仿真/PDS。实际命令和XML：`distortion/build/offline-20261024/fpga-1027-d-commands.txt`、`fpga-1027-d-final-lifecycle.xml`。

B的123综合源、RTL/私参/约束/构建助手/bit均未改，原native0/STA/130pins/bit绑定仍被文件门禁接受。唯一运行源码delta为gamma host，SHA旧470ea274536a8dd86710da1720c8167b0020441fc3553e53b322f32f7eda83b2→新3c753de644919e158ee61d47b21278f37cc718d87616cabedbc7674d9728ec8c；公共idle不变，对应tests更新。B freeze保留历史旧host，不能假称全冻结项仍是当前；新helper/测试/旧B证据关系单列`fpga-1027-d-host-overlay.json`，旧执行计划必须因helper不符拒绝。

已在禁止native/端口执行的保护下生成并文件验证一份fresh plan：`distortion/build/offline-20261024/gamma-pipeline-session-20261027T041235967878Z-4efcb772/plan.json`，0°/1MHz/UART预算30秒，executed=false。COM5为待重新核设备的历史候选端口。无主机失联看门狗；关COM/auto-off不停止视频。结束仍须固定heartbeat本次cfg_program后新DONE/新receipt；失败/失联由现场断电。四标记仍false，不因此解除pre-bit执行凭证、正式标定/光学/稳定性缺口。

**D离板里程碑完成，等待用户下一条；本轮不得执行生成的计划。** 下一轮最短是获准后核器件/COM及位流门禁，做一次DA07零角有限开发验证并恢复heartbeat；1080作为独立新target先补计数/bank与tile流水预算，再做原生MS7200采集，不并发昂贵构建。不重复C封存审计；下方C/B保持历史。

## FPGA-1027-C：DA07/K320离线候选已封存；完成本里程碑并等待

本轮只有只读文件审计及文档归档，无仿真/PDS、下载器、JTAG/串口、采图或Flash；RTL、私参、helper和bit均未改，安全/计费设置未动。B候选仍为下方同一目录、原生整数0、125MHz最终保存DB→唯一最终STA All Constraints Met→bit、130pins及源/参数/位流完整绑定。中间after-hold false及历史失败原样保留。

封存`distortion/build/offline-20261024/fpga-1027-c-seal.json`，SHA256 `0a1f6138399ad3f985bf7c5ce7002fe829415265e299df3164dfc7e59bcaaa0a`；137源/helper+14外部证据共151项与B冻结一致，零差异；候选57文件全SHA/字节数/mtime和22份历史失败日志/回执快照已记录。完整45PASS和A三套PASS只核验复用，无重跑。

四标记保持false：PreBitGateExecutionProven缺本次PDS运行期“读取最终STA并决定是否gen_bit_stream”的执行凭证；HardwareReleaseAllowed是未正式放行的开发模型；NewLensCorrectionVerified没有本次连续主版光学验收；CalibrationAccepted因11train/5held、上方/右侧覆盖不足及约束双系数模型。后两类放行标记的现有生成器没有自动转true入口，不能改旧JSON。下载前事后门禁能严格拒绝其范围内原生/日志/源hash/仿真/唯一最终STA/130pins/bit不合格，但不能证明pre-bit执行或代替现场/正式验收。

发现的实际边界：主session未在候选下载前检查idle退出计划旧receipt，到恢复入口才拒绝；45项未覆盖此例及完整会话生命周期。未来SRAM前须先只读确认主result、candidate/idle receipt不存在且计划从未使用/无并发，否则停止；若改helper须重新建立相应检查/绑定，不绕过旧哈希门禁。本轮不修已验证helper。

交接和最小短时SRAM清单见`distortion/output/project/DA07-K320离线封存与短时SRAM交接-20261027.md`：用户返回后先确认硬件身份、外接电源、40针/FPC/方向、模组镜头未变和可现场断电；再审核一次0°/UART≤30秒的开发SRAM事件与专属固定heartbeat恢复计划。本轮未生成或执行该计划。没有主机失联看门狗；关COM/auto-off不会停视频。恢复必须有本次固定heartbeat的cfg_program成功后新scan DONE=1及无清理错误，失败/失联即状态未知并由现场断电，不能用旧23:45回执冒充当前状态。正式标定仍须补独立姿态/源图覆盖；720模式另标定。

**C已完成，当前仍只允许离板文档工作并等待用户下一条，不自动接板或下载；11:49到来不构成执行授权。下方B为本次候选构建证据，A与断电段为历史。**

## FPGA-1027-B：唯一一次fresh PDS已通过，严格仅离板并等待下一条

用户授权A之后的下一里程碑：先补日志门禁完整合并回归、冻结输入，再只启动一次fresh PDS；不访问开发板、不下载/采图/Flash，不改安全或计费设置，完成后等待下一条。A确只有42项首轮41PASS+单项复跑及另3项，故B已补**单次完整45PASS／exit0**，XML `distortion/build/offline-20261024/fpga-1027-b-gates.xml`。A三套PASS及源码/参数证据核验复用，未重跑整体仿真。

DA07/K320私有13参数/guard6530716、约束、helpers及仿真已冻结，记录`distortion/build/offline-20261024/fpga-1027-b-freeze.json`；137项源/helper和14份外部证据前后逐SHA一致，123综合源前后相同。125MHz和原约束未改。02:52:34Z只读检查PDS/JTAG进程0；随后仅一次标准完整PDS于02:53:02Z开始、03:24:34.990995Z结束，原生退出0、wrapper退出0、Passed=true、非timeout。fresh目录`distortion/build/offline-20261024/gamma-pipeline-da07-k320-build-20261027-b`；未重试或另开PDS，结束相关进程0。

最终STA唯一报告为该目录`report_timing/corrected_gamma_pipeline_d5.rtr`，SHA FE9CF020AB38D0C273BF0767898DCBF88D63B6519BFE04A1DD1CC9E896085A56；唯一Input为本次最终保存的`place_route/corrected_gamma_pipeline_d5_pnr.adf`，唯一Design Summary为All Constraints Met。核心125MHz/8ns；slow setup/hold全局最差+0.312/+0.148ns，fast setup/hold全局最差+1.821/+0.106ns，各summary失败端点0。早期after-hold摘要仍false，已保留；不混用为最终DB结论。实际130个引脚/方向/唯一pad通过，D5=AA23、UART_RX=B24。

实际最终资源：LUT20642/66600（30.99%），FF20409/133200（15.32%），APM79/240（32.92%），DRM20.5/155（13.23%，保留PDS原始小数），IO130/300（43.33%）。该值属于当前完整候选，不宣传未经同条件比较的资源收益或实测FPS。

位流为该目录`generate_bitstream/corrected_gamma_pipeline_d5.sbit`，SHA `00C582168AB4395E2D43919D69DFF429D9F949CAC253DC6BDBE528406E661DF8`；validated-build SHA9B3EB24CB504AB5E11737A8A25F3B08EA5699303993E959578EFFA88835E21C1。日志审计实际6阶段成功，恰12条固定前置解析诊断，真实执行段无错误；pre-bit Tcl执行证明仍false，下载前事后门禁已通过。文件层`gamma_pipeline_session.validate_target`（不访问设备）连同真实封存native0回执已实际通过。

独立最终审计`independent-final-audit.json` SHA03726DA520E540C6616F082C63278847924A4D5DC91D6653B7E92F9C93D165FE。总报告`distortion/build/offline-20261024/fpga-1027-b-result.json` SHA6CA99E80E54097E5BD89C8453427861EAE831F46C9E9544F32AAB6290BA8ABC5；真实wrapper命令、原生argv和退出码见`fpga-1027-b-commands.txt`。原始日志、所有失败历史和A证据不改写。

**B里程碑完成后等待用户下一条；本轮未下载、采图、扫描或访问开发板，未写Flash、未改安全/计费设置。** 当前仅离板构建/STA/引脚/源参数位流绑定通过；硬件身份和供电未独立复核，实测新帧率/延迟/稳定性及正式光学校准未通过，K320仍为裁剪开发模型。下一阶段须收到新指令，并先核硬件身份/电源与精确绑定，才能安排有限实板验证；不得自动下载。

## FPGA-1027-A：重新接板声明已收到，本轮仅离板前置验证

2026-10-27用户明确报告已重新连接开发板；这是操作员声明，本轮未独立扫描身份/电源。用户同时限定只核最新源码/参数/结果/进程、修复主线日志门禁、完成DA07所需定向检查与三套整体仿真，**不启动PDS、不打开COM/JTAG、不下载、不采图、不写Flash、不改安全设置；完成后等待下一条。** 下方断电限制属于历史，不能据06:00或旧待机回执推断当前硬件就绪。

起点核对：当前compact仍为DA07，123源/13个K320整数/guard6530716与交接一致，development=true/calibration=false；原DA07单元10PASS的6项源及日志完全匹配，可复用。最新真实原图仍为已独立核验的720p单帧；H实际失败−1.140ns/59端点保持，不按旧E返工。本轮启动前相关进程数0。

本轮前置里程碑已完成，等待下一条，不继续启动PDS或板上工作。主线日志验证接入显式canonical_main/main_reseed角色；固定12条前置解析诊断单独识别，运行期E/F/ERROR/FATAL继续拒绝，H真实失败仍拒绝。builder保留源/位流/130pins门禁并要求唯一最终STA，日志助手进入哈希闭包；session增加真实封存Passed/native整数0/未timeout/无清理错误/当前源前后及manifest哈希的核对。未改变RTL、约束、安全参数、Flash策略或标定数据。

45项定向检查最终通过（46次执行）：首轮41PASS+1条测试自身Path类型断言失败，修复后只复跑该项PASS；另3项封存native结果检查PASS，原失败XML保持。原DA07单元10PASS直接复用，没有重复大套。

DA07新small/video/native三套整体仿真实际exit0，报告`distortion/build/offline-20261024/gamma-pipeline-sim-20261027T022808162491Z-406441/gamma-pipeline-integration.json`，SHA D34BE9828DF7590502EF3B040F8446DE0081E773E9BE8BD8829AFCFEC1B80C41。三套均PASS，128项监视源前后及当前相同；12角3686400像素/CRC匹配，最坏2565884模型周期，builder已接受exact current sources。native真实输入仅GM0，Gamma1/2由small合成场景覆盖；这不是实测FPS、最终时序或光学标定通过。

本轮完整结果为`distortion/build/offline-20261024/fpga-1027-a-result.json`（SHA794F5D0F5BD6FF65298B8D9632EDB84738366300649B4F75E3D03CE7FC808386）；真实命令、退出码与XML路径在同目录`fpga-1027-a-commands.txt`及结果JSON。开始/结束相关进程数均0，未启动真实PDS或访问设备；没有生成新位流。下一步待用户新指令安排fresh DA07 PDS，最终STA/引脚/身份电源/位流门禁未完成前不得上板。

## 当前限制：只允许离板工作，等待用户明确重新接板

用户通知今晚00:00–06:00断电，要求从现在起停止新下载、Flash和板上采集。**禁止扫描JTAG、打开串口、下载或采图；仅允许源码、CPU/RTL仿真、离线PDS。06:00到来不构成恢复授权，必须等用户明确说已重新接板。** 已明确告知用户现在可以断开开发板电源。

断电核对：2026-10-26T15:54:57Z（北京时间23:54:57）未发现JTAG服务器、下载客户端、PDS或项目采集进程。最近720会话passed=true、com_closed=true，program/idle清理错误均空；最后固定heartbeat新DONE为15:45:42.766177Z（23:45:42）。无Flash写入。限制记录为`distortion/build/offline-20261024/hardware-access-hold-20261026.json`。

源码已原位保存；当前主123源及720的109源闭包核对通过，SHA清单`distortion/build/offline-20261024/power-cut-source-checkpoint-20261026.json`。未提交/推送、未清理或移动既有文件。main compact最终SHA为`da07e9ac7efa0ca53fd470c47b74039276de35069c5bb8f77ed8620565c2e531`：slow SELECT→CHECK寄存及RAM地址mux化简，离板单元10PASS，prepare硬钉已同步。**DA07尚未跑新整体仿真、最终PDS，更未上板。** H实际时序失败为−1.140ns/59端点，对应slow_y→地址乘加→tag比较→valid_lines；失败证据保持。

离板下一项：解决main日志验证器对固定PDS前置解析错误的误拒；新`pds_gate_log_audit.py`只支持钉定H/raw720脚本，不能盲套新入口。随后以DA07/当前真实开发参数跑新三套整体仿真、fresh PDS与资源核对。全部通过后仍不得下载，等待重新接板授权。

## 最新实物成果：1280×720原图已完整回读

真实会话`distortion/build/offline-20261024/raw720-cam2-20261026T154116684410Z-21059f01/result.json`通过：1帧1843200B、CRC9352459D、57600个DDR beat，8状态+4命令，完整接收文件1844268B。独立struct/zlib及PNG核验921600像素零差异，完整88角点可检出；审计`independent-native720-hardware-audit.json` SHA9CE8F61BA41952093306A18958FB1791B1FD56CCA9A5677CBCA70A23D3A9F2BC。当前原图桌面在下、显示器在上，直接0°显示，不能盲用旧VGA的180°；未纳入正式训练/留出。

图像为同目录`raw720-31539416-CAM2-frame0000000001.png`。位流SHA为`25672eff0d628351af789c5a3f3ad749d0a8f5fc0df771dc2b914ea904c7e41a`；最终资源LUT10315/FF9727/APM1/DRM12/IO129，HDMI仅诊断色条。完整成功post-validation回执已保存，原builder false及日志保持。单帧不证明15fps、720实时矫正、显示或长期稳定；720无正式K/D，不继承VGA标定。下方H进行中、720未实板等内容为较早过程，以本节为准。

更新日期：2026-10-26。用户已更换OV5640摄像头，确认仍为同一40针接口、同一方向、未改接线；新模块CAM2已实采640×480 RGB565原图。GP200标定板已在场，标注12×9-15，实图检测为11×8内角点。新模块CAM1尚未复测，下文原CAM1的3018失败属于换机前历史。接口逐针/电压、商家200°视场、同步和物理左右仍待验收。

新模块真实标定采集已暂告一段落：T01加首批14帧、补拍5帧共20候选图均保存，两批传输与STOP均通过独立核验。采集结束恢复heartbeat的新DONE为2026-10-26T03:04:03.245188Z；后续实际板上事件见下方。质检保留11个train、5个held_out；T03近重复，T05/T07/T15未检出完整88角，仍缺原图上方/右侧覆盖。首次四系数拟合还出现T10病态矩阵，正式标定未完成。索引为`distortion/build/offline-20261024/gp200-cam2-20view-quality-review-20261026.json`和`gp200-cam2-selected-manifest-20261026-v2-incomplete.json`。

用户已离开，标定板重新放回中间；本轮停止需要用户移动板子的采集，继续离线集成和显式开发用拟合，不降低正式12训练姿态/覆盖门槛，不把held_out改作train。用户指出预览倒置且桌面遮挡物理低位：原始像素仍供标定，后续预览须在显示层独立转换方向并先核实，不能再直接把原图坐标当用户看到的方位。新模块身份为`replacement-20261026-cam2` / `replacement-20261026-lens-cam2`，不得混用旧镜头数据。

用户晚上回来后要求继续自主推进，只在明显成果或必须现场操作时通知。当前不再催补VGA边缘姿态：先完成连续VGA主版与独立720输入，待参赛输入模式确定后集中做对应正式标定，减少重复摆板。720p不能默认继承VGA内参；当前开发/覆盖未通过状态保留。

现有图已得到明确开发用的约束双系数模型（k3=k4=0），train RMS0.181px、held均值0.126px/最大0.257px；留一10成功/1失败、80度请求域失败、T10四角超OpenCV逆域，均保留。Kout320工程网格的13角×307200全帧数值近似最大0.198px，零失效/折返，但有明显裁剪；不代表正式标定、完整视场或FPGA实物输出。最终canonical索引为`distortion/build/offline-20261024/gp200-cam2-development-K320-canonical-handoff-20261026.json`；显示用页面`gp200-development-K320-viewer-20261026.html`仅CSS180度，安装方向仍待用户现场确认。已修复数值审计把开发来源误标candidate-ready的问题，正式就绪继续为false。

主候选PDS A于03:32:24Z触及1200秒上限，原timeout/native-null失败保留；B复用map/plc后重新布线，仍有未连线，04:33:30Z由root精确核对所属PDS进程及父runner后停止，以转向已验证的紧凑缓存。B为native1/非timeout、无validated-build，前后123源及输入DB一致；放弃理由见B内`root-requested-stop.json`。旧B将被改动的4份生成输入保存为`precompact-*`，没有改写历史失败。

当前主线已切到compact INDEX5：两组16bit共享像素RAM，无重复快缓存/回退缓存；同条件map由LUT21290/FF20168/APM85/DRM28/IO130降至20988/20075/85/20/130（`gamma-compact-index5-map-20261026-a/map-result.json`）。这只是map与首个流水候选的对比，DRM与旧完整主版的20相同，不当作最终route或已测板FPS。compact INDEX5历史12角全3686400像素/掩码/CRC通过，最坏3701230模型周期；INDEX3虽像素正确但最坏8451070周期超预算，未推广。

紧凑缓存及canonical K320开发参数已正式合流到当前源码，仍为123闭包，稳定122源未改。新三类定向仿真均通过（`gamma-pipeline-sim-20261026T044035726647Z-ceac62/gamma-pipeline-integration.json`，SHA49DEDBBA3C53121A631230D1622E03B48509054612608AF8737C5F03B299F734）：small含Gamma0/1/2、video三时钟所有权/故障、native使用真实T01/T04/H03生成12角独立golden逐像素验证。开发/覆盖失败标记仍保留，不能将其称正式光学验收。

C完整PDS结束但最终时序失败：slow setup WNS−4.002ns，5726个违例端点；生成的位流已标记DO_NOT_PROGRAM，未下载。关键路径是当前坐标经缓存命中判断返回算术流水使能。已在compact输入增加两项FIFO，将in_ready限于寄存状态，切断该组合反馈；没有改内部采样算法。新增bitstream前时序门禁会直接拒绝失败报告。FIFO2完整三套仿真通过（`gamma-pipeline-sim-20261026T060105804012Z-71fe99/gamma-pipeline-integration.json`，SHA182C23BA775969E6AD11411C08DE93FD4F16AC5703AC7EBF513EDFED61E052B2），真实来源12角3686400像素逐一匹配，模型最坏2482918周期；不当作实测FPS。

E完整PDS于2026-10-26T06:35:54Z结束，位流前门禁按预期阻断：slow setup−2.757ns/320个端点（比C的−4.002/5726减少），hold通过，无位流/validated-build，未下载。目录`distortion/build/offline-20261024/gamma-pipeline-compact5-k320-build-20261026-e`；binding为`gamma-pipeline-compact5-k320-development-20261026.binding.json`。独立双审确认FIFO2切掉旧mapper→全局CE路径；剩余最差5条都为FIFO read_pointer→XY选择/像素乘加→tag比较→DRM地址。当前只修改compact，增加一级弹性decoded-query寄存，保持125MHz/算法/精度/公开FIFO2；三助手/Tcl/私有参数保持。随后重跑三套整体仿真和全新PDS，最终130pin/时序/位流SHA通过再上板。尚无本次连续主版板FPS或端到端延迟结论。

E真实最终route资源为LUT20739、FF20215、APM79、DRM20、IO130；这是时序失败候选的占用，不能称可用主版。相对旧稳定版并非同参数/同实现条件，APM变化不单独当优化收益。

地址预解码修复已完成：compact SHA `d20cc1618028b03d186fe28fddf4a3df68bcd2e311b827f7573fd90773fdf1a3`，公开FIFO2不变；新增一级elastic pixel_number/bounds/XY/fraction/TAG寄存，live命中判断未提前锁定。定向仿真9PASS，含WIDTH639/负坐标、decoded停顿/换帧排空、原640/1024冲突和DDR故障；prepare门禁测试4PASS。新三套整板仿真`gamma-pipeline-sim-20261026T142424973313Z-1ccbec/gamma-pipeline-integration.json`通过（SHA18A2678B2ED96D597CE7545CA107BA4C25C85F373CC006B96F9DBE84A7E11531），实际三来源12角3686400像素匹配，最坏2482918模型周期；独立审查源码/fixture/日志及E→F差异通过。E的原prepare另存`before-decoded-query-prepare.py`，失败历史保留。

F布局seed2在4根未连线上超过50轮不变，于15:11:22Z由root核对Python30608→PDS32828→router3392/自有console31296后停止并封存；native4294967295/非timeout/123源前后相同，无validated-build，未下载。`root-requested-stop.json`保留进程/输入DB证据。G尝试map-only重新布局未真正启动PNR，native1且无DB，失败保持。当前H（`gamma-pipeline-reseed3-build-20261026-h`）采用确定的完整compile/synth/map/PNR流程，派生脚本与固定主Tcl只差seed2→3；主123源/三个助手/Tcl/参数全部冻结，实际最终时序和FPS仍待完成。

独立720p15采集候选已完成109源/129引脚及全帧数字集成（921600像素、42状态包、CRC B41545F0），新tag52373201；单bank base0/2MiB，独立720身份不继承VGA K/D，HDMI仅诊断色条。`raw720-cam2-build-20261026-a`实际PDS native0，最终保存DB时序AllMet，资源LUT10315/FF9727/APM1/DRM12/IO129；原builder因初始项目预解析的12条gate错误而false。12条仅在实际flow前，真实六阶段无错误，已独立事后复核并保留原false：post-validation-receipt SHA2CA168B0465F5DB1E290C1F485B3D7EBAA4ACC9C0FA9996CDF654258F194B9AA，validated-build SHA655212E0570A5794F12956DDA610A84F43E6EF80A2D8E75FE43FEE6FA962E1D1。位流SHA72EFF0D628351AF789C5A3F3AD749D0A8F5FC0DF771DC2B914EA904C7E41A。尚未进行720实板；名义15fps和PLL锁定未实测。

门禁证据修正：纯Tcl检查通过不能证明PDS实际执行自定义pre-bit检查。实机PDS在项目预解析时尝试打开尚未生成的报告，生成的impl.tcl未保留这些通用语句；当前将其标为PreBitGateExecutionProven=false。实际下载必须依靠原始日志分界、native退出、最终保存DB时序、全部引脚/源/位流哈希的独立事后门禁，不能把脚本预解析错误当真实时序失败，也不改写原builder的false记录。

独立图像回读目标gamma_capture_k320_dev已通过完整PDS并实际运行：`distortion/build/offline-20261024/gamma-k320-session-20261026T053455435632Z-f993419e/result.json` passed=true；同一真实输入的raw/矫正/Gamma三包共1843332字节，CRC全部通过，两个输出各307200像素与独立参考差异0。实际自动触发Gamma1，矫正图平均亮度19.43→40.84；不代表信噪比或细节恢复。开发模型和裁剪限制继续保留；这次不是连续显示主版验收。实际图像预览为该目录`physical-triplet-preview.html`，CSS180°可切换，原始像素不变；方向待现场确认，浏览器渲染尚未核验。

当前最后确认板上事件为2026-10-26T05:37:38.265268Z（北京时间13:37:38）重新下载固定heartbeat后的新DONE=1，串口/JTAG已关闭；之后状态不连续观测。上述真实三联图已完成独立包结构/CRC/PNG/源码/下载回执审计。没有写Flash。

用户晚上回来后已再次只读扫描：`live-scan-20261026T141742247790Z/scan-result.json`于14:17:52Z通过，PG2L100H/00602899，无编程/相机写入，工具正常退出。只证实JTAG当前可用，不当作新的heartbeat配置或持续状态。

## 当前首要方向：主功能、吞吐与资源交付

用户明确不再细究坏摄像头，现已换好摄像头；先用新模块可工作的CAM2。已更新`distortion/output/project/项目总览与冲奖交付清单-20261026.md`，暂停原CAM1诊断支线。当前完整Gamma与compact FIFO2缓存已合入独立候选`corrected_gamma_pipeline_d5`，私有include已绑定本次K320开发参数，三类整体仿真通过。双目/深度后置；不再为每步重复大套、长报告和总封包。

高分辨率路线已核对数据手册：OV5640并口PCLK上限96MHz，8位DVP/RGB565的1080p30有效数据本身需124.416MHz，因此当前格式路线不能原生输入1080p30。下一档优先720p30；现720p15初始化、PCLK域整帧准入及组合frontend已有数字仿真，尚未形成完整720p实板链。720p30条件模型84–94.5MHz在传感器额定以内，但超出旧48MHz约束，必须先验证板级采样和新约束。1080p需另行确认可用的高带宽输入或像素格式；来源和边界见`distortion/output/project/ov5640-dvp-resolution-priority-20261026.json`。

真实route资源已核：旧完整corrected_gamma_d5为LUT20097/66600、FF19830/133200、APM83/240、DRM20/155、IO130/300；新guarded raw为9685/9261/2/44/129（各容量相同），不同位流不相加。parity的36→28仅为另两个流水候选的map对比，不能说主版省22.22%。完整资源出处和旧目录时序报告差异见总览及资源JSON；新主版统一重建确认。

## 10月26日新事务诊断已实板完成

- 入口`distortion/output/project/CAM1事务诊断实板结果-20261026.md`。用户更正此前FPC确未插紧、现重新插紧；原完整CAM1仍35状态/0TX/0RAW/61@3018/262，CAM2单帧91C0B90E通过，均保持原位流与full7FF0/quarter68。
- 新独立6脚register-only目标已通过7类真实总线仿真、两例实际UART318包、最终PDS与实际引脚/方向核验；源8，位流SHA037BFC02535E6B6AF2E0CA2A788D6360E750DE4F095879F695D7E801E2554579。slow setup/hold31.794/0.204ns；无RAW/DDR/HDMI，完整输入仍未恢复。
- 新实板run`cam1-transaction-20261026T010129957076Z-924261cc`：24完整64B+末1B/1537B；3018写bus_error0，随即读bus_error1/无效00；失败后300A/300B各error1，最后3018读error0/有效00；只探测三次，原failed61/262保持。24包保持同一次事件，不是24次试验，不据此判定复位/供电根因。
- 独立实板审计和132文件exact snapshot均已保存，snapshot SHA372ab41ab8bdb674961e5f324ad32fc774a0b00bca776538d86446e08a139477。默认only-plan另存，不当成硬件事件。新增适用测试34（时钟模型）/61（协议主机）/15（builder）与原712+9/local122分开，未宣称云端CI运行。
- 当前最后确认SRAM事件为2026-10-26T01:02:39.877422Z（北京时间09:02:39），诊断结束关闭串口后重新下载固定heartbeat、新scan DONE=1。未写Flash，之后不连续观测；原guarded/host/codec和生产init未改。
- 该诊断阶段标定板尚未到货；当时提出的CAM1等待对照已被上方最新主功能优先级取代，不再作为当前下一项。后续新模块及GP200已到场，当前采集/开发标定状态以上方最新记录为准。完整720p与正式新K/D仍未完成。

## 10月26日恢复开发初期记录（复测已完成）

- 用户明确恢复开发，并更正此前FPC确实未插紧、现在重新插紧。先前失败按当时状态保留，不把前次插紧声明当成已经验明接触。新只读扫描`live-scan-20261026T003305109324Z`识别PG2L100H/00602899。
- 原完整CAM1限额一帧尝试`guarded-native-20261026T003331333200Z-59bde393`仍35状态/4480B、61@3018/262写入、未ready；未授权而零TX/零raw，capture失败保持。新CAM2对照`guarded-native-20261026T003723128287Z-a0b06727`单帧通过，12状态+1VGA/615980B，CRC91C0B90E。原位流、quarter68/full7FF0不变；原guarded/host/codec未改。
- 本阶段最近确认的SRAM事件为2026-10-26T00:38:33.963407Z（北京时间10月26日08:38:33），CAM2结束后的固定heartbeat、新scan DONE=1；后续新诊断实际构建/下载见上节。
- 暂停前的新诊断初始化器已完成真实reg16_i2c线路仿真7例、2074事务与旧初始化器逐拍对照；新720p有序时钟静态工具34测试通过，仍不授权硬件。新增PGCAMD01协议/有限主机工具适用61测试通过。计数独立于原712+9/local122，未宣称旧全套覆盖新代码。
- 当前工作：独立6脚register-only诊断整板目标与2例真实UART仿真，之后最终PDS/引脚与源码核对，再受限上板读取写/读/probe结果。它不包含RAW/DDR/HDMI，不替代完整8位输入验收。CAM2真实标定主线仍等待实际标定板数据。

## 用户断电暂停点（已于10月26日恢复）

- 用户明确“要断电了，尽快暂停，我们明天继续”。已停止三个离线子任务，不再启动下载、采集或测试；不安排自动恢复。
- 本轮实际板上试验均已结束。最后确认SRAM事件仍为2026-10-25T15:52:27.188588Z（北京时间23:52:27）：CAM2单帧结束后重新下载固定heartbeat，新scan DONE=1。允许用户断电；断电后的实际状态未观测，明天不能假定SRAM配置仍在。
- 已完成：用户声明插紧后、恢复供电的原CAM1复测仍61@3018/262写入；CAM2新单帧D626F207通过。两份独立审计和两场景索引已保存，入口`distortion/output/project/FPC插紧后复测与诊断推进-20261025.md`。上电前的扫描失败单列，不计CAM1初始化失败。
- 未完成草稿：`distortion/tools/ov5640_clock_sequence_audit.py`、`distortion/rtl/experimental/ov5640_cadence_diagnostic_init.v`及正在准备的相关测试/TB。中断时尚未收到并独立核验最终测试/仿真报告，统一视为未验收；未构建或下载新诊断整板目标，也未实现完整720p模式。原712+9/local122回归不能覆盖这些新增草稿。
- 明天先核对当前文件和未完成测试，再完成CAM1独立写/读/pending状态诊断与最多三次只读探测的真实总线仿真；随后做整板准入。720p工具先做有序静态模型及反例测试，复位未知区间、低VCO可用性和模拟锁定不得冒称已证实。设备重新供电后先只读扫描，再按实际任务下载；不机械重复插排线。
- 本轮未完成新的总成果包，不覆盖此前`repower-reset-isolation-20261025.zip`。源码改动均留在本地，未提交/推送。

用户明确11月4日最终提交，须在此前完成；按任务和验收推进，不按日期冻结或预估问题工期。新增工作已含实际RTL仿真、旧板CAM2参考约束下的整板位流构建及本轮新模组CAM2两帧真实原始采集/恢复待机；详见下方现场记录。本地起点为`feccb4885e9178a18493c9f2b7a4f5d5a6cc2a9c`，新增工作未提交/推送。

## 10月25日FPC插紧后复测

- 用户声明FPC已插紧，随后澄清先前尚未供电、现已开启。首尝试`guarded-native-20261025T154810150553Z-7454434d`仅停在无FPGA的JTAG扫描：没有编程、没有开COM，也没有heartbeat恢复，不计新CAM1初始化失败。上电后`live-scan-20261025T154912645082Z`以1MHz只读识别PG2L100H/00602899。
- 有效原CAM1复测`guarded-native-20261025T154934582558Z-7aca0fbb`仍20状态、61@3018/262写入，零主机TX/零raw；原位流D876、quarter68/7FF0/readback不变。后续CAM2 run `guarded-native-20261025T155112842393Z-86055e74`实采一帧通过，615852B=11状态+1VGA，CRC D626F207，唯一一帧预算及排空通过。两轮全source/引脚/字节/快照及退出回执已有独立审计，见`distortion/output/project/FPC插紧后复测与诊断推进-20261025.md`。
- 目前错误61只保留3018写后校验读首设备地址未应答，未保留这笔写的pending末位高状态；verified_noacks=0不证明该次write完整ACK，observed00也无有效读值资格。下一步新增独立诊断初始化器及真实总线仿真，分别记录写/读和最多三次只读探测，失败保持，未形成新整板目标/下载；原guarded/host/codec源保持。
- 当前最新确认SRAM事件为2026-10-25 15:52:27.188588Z（北京时间23:52:27），CAM2结束后的固定heartbeat，下载后新scan DONE=1；之后状态不连续观测。FPC插紧为操作员声明，未拍照/测通或确认物理左右；不再把它写成已排除接触问题。
- 本轮两场景索引`distortion/output/project/guarded-fpc-reseat-campaign-20261025.json`完整性通过，场景1/2通过，CAM1失败保留；此前证据包不覆盖。新增诊断和720p离线模型的适用测试与原712+9/local122完整回归分别记录。

## 10月25日重新上电与复位隔离（前一阶段）

- 用户确认重新上电，另说明FPC/锁扣状态不确定，接触操作未确认。本轮原CAM1复测仍61@3018/262写入；新增将参考CAM2 reset Y20持续拉低的独立目标，原CAM1 quarter68/7FF0/init/readback不变，实板仍同故障，均零UART授权/零raw，失败原样保留。
- CAM2另行实采640×480一帧通过，CRC F8CA1A3D，全部RAW/PNG/107源绑定核对完成。当前主线输入可用，不等于颜色、真实标定或同步双目通过。见`distortion/output/project/重新上电与复位隔离复查-20261025.md`。
- 第5目标`raw_camera_capture_cam1_guarded_isolated`源107/实际130脚，新增Y20 inout常0及4份复位参考均封存；FPGA控制意图不等于新模组实物已隔离。位流SHA `668901F16165638AE58A4E7E8AEDD0C34A115468CB98030E72C056986EC9BBC0`，最终时序core setup/hold1.130/0.137ns。不得由无恢复排除所有另一传感器影响。
- 新host SHA `455ceb50fe71763ae0b2b539076c6184dfe4c7e90ab90e608d6620262b98ac2f`，codec SHA `913a964fb99b4f2715b60055aa76657c39d77eca7f1c59d0e2deb9aa4f3b33a3`；默认CAM2及旧4模式门禁保持。新回归portable31文件712项+9子测试，local6文件122项通过，521监测文件不变；报告`cpu-final-isolated-20261025-232928-428621/final-cpu-report.json`（已批准scratch下）。
- 本阶段最后确认SRAM事件为2026-10-25 15:28:29.405700Z（北京时间23:28:29），隔离试验退出后的固定heartbeat，下载后新scan DONE=1；后续FPC插紧/供电澄清及新下载见上节。该阶段尚未确认锁扣状态，当时下一项为连接器近照；CAM2几何主线和720p离线实现独立推进。
- 本轮三项索引为`distortion/output/project/guarded-repower-and-isolation-campaign-20261025.json`，完整性通过而场景通过1/3；本轮包`distortion/captures/repower-reset-isolation-20261025.zip`及同名`.zip.manifest.json`均独立新存。原始失败与各自历史helper版本不合并抹平。

## 10月25日CAM1单变量诊断与计划调整

- 入口：`distortion/output/project/CAM1单变量诊断与计划更新-20261025.md`。新增独立SCCB25目标，只改quarter68→270，7FF0/PLL/readback/129引脚不变；107源及最终时序通过，位流SHA `DE927EAB5479A6FA7A00EBEA7502053FD391C2B8564F8D15C7B8C3941BDA87AC`。
- 实际run `guarded-native-20261025T144841727252Z-e06d0f11`，20个CRC状态仍为ID5640、错误61@3018、完成262写入；零UART命令、零raw，`result.passed=false`保留。本次降速不足以恢复，不扩大为全部时序排除或物理根因判定。下一项断电核查摄像头模组两条FPC插接/锁扣，再完整输出基线复测。
- 新host SHA `686dce83e0f3012d78cd6544b3578ab85a734610638e17fe4a15127eaeb552b2`，codec SHA `fd46fcb1ae6928468ddc09ada82717d29ffcecde34459944a942d1328a960827`；前三模式及默认CAM2保持回归通过。重新合并CPU31文件669项+9子测试，本地4文件91项通过；406监测文件前后不变，旧raw97/各目标绑定保持。不是继承旧632，未宣称云端CI运行。
- 720p来源研究新增自洽时钟模型分支，见`ov5640-720p-bounded-clock-source-plan-20261025.md/json`；尚未实施/测频，旧840MHz移植仍阻断。计划调整为CAM2几何主线优先，颜色准确度、CAM1及720分别验收；当前原图不等于真实标定。
- 本阶段最后确认SRAM事件为2026-10-25 14:50:05.509207Z（北京时间22:50:05），SCCB25失败退出后的固定heartbeat，下载后新scan DONE=1；后续重新上电/复位隔离见上节。历史两批成果包均不覆盖。

## 10月25日开灯后补采

- 用户确认已开灯并将摄像头固定朝向房间。CAM2按原guarded位流实采两帧640×480，房间/桌面清楚可见，近黑像素分别2.993%与3.046%；场景/朝向/照明均有变化，不作因果改善率或颜色合格结论。原图呈侧向，接收端没有旋转、矫正或Gamma。见`distortion/output/project/开灯后原始采集-20261025.md`。
- 实际run为`guarded-native-20261025T141320078036Z-e10c654c`；完整wire1230424B，12状态+2原始帧，CRC为1ABF927C/6257671D。单次两帧授权后admitted/completed=2、最终预算0，全部原始像素/PNG/107源绑定通过；原host/位流未改。未生成K/D。
- 本阶段最后确认SRAM事件为2026-10-25 14:14:39.565664Z（北京时间22:14:39），本次采集退出后的固定heartbeat，下载后新scan DONE=1；后续SCCB25事件见上节。此前9轮成果包保持原样，本次另存补充记录。
- 独立审计`independent-lit-room-two-frame-audit.json`通过全部像素、命令/预算、源码/引脚/时序、下载及退出回执核对。补充证据索引为`distortion/output/project/guarded-lit-room-capture-20261025.json`，补充包为`distortion/captures/lit-room-capture-20261025-v2.zip`；先前632项CPU结果属于同一冻结代码，未为此次只采图/记文档重复跑全套。

## 10月25日持续开发成果

- 入口：`distortion/output/project/持续开发成果-20261025.md`；9轮实板证据索引为`distortion/output/project/guarded-campaign-20261025-final.json`。七项CAM2默认未授权、QUERY、短租约、重复GRANT、STOP排空、授权后停止TX及非法命令测试通过，每轮finally重新下载heartbeat并新scan DONE=1。另有一轮彩条传输通过、一轮CAM1启动失败；颜色码值另记未通过。有限测试不代替长期运行。
- 三个独立guarded目标均完成107源、129引脚及最终时序核对；CAM2自然图/CAM1自然图/CAM2内部彩条的身份、构建标签、来源类型明确区分。新入口为`distortion/tools/guarded_native_session.py`，默认只计划，显式`--execute`才接触设备。
- CAM1真实失败：ID5640/262写入，0x3018写后读事务首设备地址NACK（error0x61）；observed00不是有效寄存器值。未发命令、未授权、未采图，失败记录和heartbeat恢复均封存。不能通过关闭数据位或忽略readback宣布另一眼通过。
- CAM2彩条色序/字节序通过，全部307200个RGB565字与10月8日修正D5后的历史彩条一致；理想颜色码值最大差99，原40门槛仍未通过。测试图不进入标定或光学验收。
- G7实际14包TX/20份CRC状态全部独立匹配：接受8/拒绝4/RX错误2/最后seq10，零帧、零预算。非法帧数的requested_frames回显不代表授权；审计见该run的`independent-G7-hardware-audit.json`。最后host SHA为`18a937350164f27750f2c70191ce25e5a7ee3c2b53308605552cc2607cd3e493`。
- 720p完整921600像素经实际RTL raw/DDR/导出协议仿真及独立逐像素回读通过；传感器模式因VCO、RGB时钟与banding来源问题未放行，没有下载720p位流。旧4基线和原97源闭包复核通过。
- 最终31文件CPU回归632项及9子测试通过，另有本机构建检查68项、归档关联检查6项通过；267监测文件前后哈希一致。报告：`distortion/build/offline-20261024/cpu-final-20261025-195932-484300/cpu-suite-final-report.json`。CI只更新本地配置，未推送或宣称云端通过。
- 本阶段最后确认的SRAM事件：2026-10-25 11:59:55.825941Z（北京时间19:59:55），G7退出后的固定heartbeat，SHA `DF7EEC4B4E38441183B45BAF8B38D8414FDD456A5EB78FB3AEB1FD94B361B360`，下载后新scan DONE=1；后续开灯补采事件见上节。

## 10月25日接板现场推进

- 用户确认新模组接原40针接口、同方向、未改接线；原厂资料/原图/到货照片已形成配套路径工程审阅。未逐针测通、未实测电压；物理左右眼仍未知。见`distortion/output/project/OV5640接板兼容性审阅-20261025.md`。
- COM5 CP210x可打开。初次1MHz/100KHz扫描无器件，用户断电重新插紧10针JTAG后恢复：PG2L100H、ID 0x00602899；随后1MHz编程通过。失败原始日志保留。
- 已修复PDS扫描后自有server退出的生命周期问题，仅在端口空且原server已退出时启动本次第二个server；不接管其他服务。新短采入口`bounded_native_bringup.py`串联source-bound raw下载、限帧/限时接收、完整wire保存和finally heartbeat。新增本轮4组Python工具合并92测试通过；没有烧Flash。
- 实际本轮目录：`distortion/build/offline-20261024/bounded-native-20261025T092115620764Z`。取得640×480 CAM2原始两帧(每帧614400像素字节)，完整wire1228888字节；独立手解header/payload/trailer CRC和保存raw完全一致。97源/位流/引脚/最终时序独立核对。原图很暗偏绿，约86.5%像素近黑；自然场景未发现历史D5双位恒零签名，但尚未完成色彩、曝光或光学验收。
- 首采退出确认：该run的finally heartbeat，2026-10-25 09:23:20Z（北京时间17:23:20），SHA DF7EEC4B4E38441183B45BAF8B38D8414FDD456A5EB78FB3AEB1FD94B361B360，cfg_program后新scan DONE=1。该时刻之后状态不被连续观测。
- 已完成无屏诊断扩展：独立thermal_idle低负载实采20条CRC16有效ADC记录，内部近似33.794–33.916℃、OT/AL=0，未经外部校准、不代表raw温度；新camera_isp_probe_d5仅改D5→AA23等目标名，原AA22探针禁止，实际读到15轮24寄存器、AE/AGC/AWB自动且关键配置一致。
- 本阶段最后确认下载：2026-10-25 09:46:04.795694Z（北京时间17:46:04）ISP诊断退出后的heartbeat，固定SHA、cfg_program后新scan DONE=1。随后guarded实测事件见上节。两个诊断目录及SHA见`distortion/output/project/live-bringup-20261025.json`，操作入口见`无显示器自动开发说明-20261025.md`。
- 本阶段相关Python工具联合164测试通过，thermal数字模型/UART仿真及新probe最终时序通过。现场照明尚未得到确认，没有盲调曝光/增益或填新K/D。随后已集成guarded板上授权/租约/温度联锁并做受限实板测试；棋盘格标定、同步双目、长期无人值守及HDMI成品输出仍未验收。

## 10月25日实际离线推进

- 入口：`distortion/output/project/新镜头离线进展-20261025.md`。新增raw_camera_capture不含旧标定/Brown/旋转/Gamma，实际RTL已覆盖完整VGA307200像素、CRC、DDR等待、UART背压、冻结/连续重arm和故障。
- 整板候选`raw_camera_capture_cam2_ref`仅采用旧板已知CAM2参考接线：最终路由时序通过，97项源码/IP/约束/引脚绑定；位流SHA为`92F035C5DF3227AB3C51DF24A9FC3DBD614F2FBD22012A85F785971FA109BBDD`。构建在`distortion/build/offline-20261024/raw-board-20261025-130835-320`，原wrapper进程ExitCode不可用误报记录与独立revalidation均保留，不伪造退出码。
- 历史blocked模板`ov5640-cam2-reference-session.binding.json`保持原样；本轮另存provisional工程审阅绑定和成功编程后的session-binding，不反写旧模板或将审阅当作电气实测。
- 新增身份绑定的native_camera_capture接收/离线回放、单眼显式数据集到四系数内参、逐眼引脚审计与前向视场范围检查。离线回放不升级为新物理采集。
- 接板前CPU/RTL字节流历史证据见`offline-validation-20261025-ready.json`：299项测试、9项子测试通过；独立总核验`offline-readiness-20261025.json`通过。安全SRAM下载入口`program_native_raw.py`已实现且默认只计划，接板后需物理review及显式execute。10月24日及较早10月25日记录作为历史保留。

## 新镜头阶段入口

- 阅读`distortion/output/project/推进计划.md`：T0–T10主链及B1–B5双目依赖。
- 使用`distortion/output/project/新镜头离线工具说明.md`：相机准入/预算、四系数fisheye映射审计、双目配对/标定。
- 新设备未知字段保留null；不得沿用旧镜头K/D、近似系数或radius guard。camera2历史脚本是单路替换且含旧D5映射，不作为双路入口。
- 下一项：隔离CAM1启用数据输出后SCCB失败的原因；在照明明确的场景补自然图/中性目标，继续定位暗绿。T0已形成受控接板工程审阅，T1已有CAM2原始传输和彩条色序，但颜色码值及另一眼未通过；新标定仍需实际标定板多姿态数据。
- 工具通过仅证明CPU离线能力；新参数RTL、最终时序、新镜头画质/吞吐/延迟、双路同步和Flash启动均待独立验证。
- 10月24日历史离线结果：185项测试、9项子测试通过；4个历史基线审计通过；合成13角VGA共3,993,600坐标检查及域失效拒绝通过。完整命令/源码SHA/日志见`distortion/output/project/offline-validation-20261024-final.json`，临时文件在已批准的`distortion/build/offline-20261024`。

## 旧镜头稳定基线（历史结果）

- 稳定演示版本：`corrected_gamma_d5`，640×480、核心125MHz。
- 关键修正：摄像头D5应为AA23，AA22版本只作历史对照，不再下载。
- 稳定位流SHA256：`069D8ACEF8DED0CD62D19EE47C83E06910DF35BD0D76A9DF29403A8A14B877CF`。
- 最新现场记录截至10月9日：零角度有限短测约18.39新增矫正帧/s；12角度短测约15.98；HDMI约60Hz含重复刷新。有限测试错误计数0，不代表长时间验收。
- 修正后中心、左、右棋盘已有单组同源观测；完整画质、斜边清晰度、重复测量和全视场验收待补。
- 缓存候选的仿真成果与未完成路由分别保留，不替代稳定版本。
- 旧轮次最后记录：2026-10-09 22:55:08下载heartbeat待机；当前本轮配置事件见上方10月25日现场记录。
- Flash自主启动未验收；现用易失SRAM下载。

## 历史后续事项的当前状态

1. 阅读`distortion/output/project/成果记录.md`、`实验操作表.md`，确认哪些结果仍待验收。
2. 补D5修正后的独立标定、中心/四边重复几何、斜边和真实强弱光实验。
3. 对缓存或帧调度选择一个候选完成最终路由和同条件实板A/B。
4. 测延迟与持续稳定性；提高分辨率前先确认输入和DDR预算。
5. 原10/20、10/26、10/30日期节点已由按任务验收推进的新计划替代，最终11月4日前完成提交。

## 每轮交接填写

- 接手人、日期和起始提交：
- 本轮改动及提交：
- 通过的检查和原始证据位置：
- 未通过项及影响：
- 板上最后下载目标、连接和版本：
- 下一步第一项任务及对应入口：
- 新数据/位流是否已随代码提交或发布附件：
