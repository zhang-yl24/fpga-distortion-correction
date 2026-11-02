# 720p物理检查接续（2026-11-01）

继续`codex/camera720-output`，已推送阶段提交`05c5b19`。用户要求继续完成720p离线检查，需要上板时再通知；本轮没有访问开发板。先720p清晰度与该模式矫正，再提高帧率的顺序不变。

## 已推进

- `reset-save-ready-a`实际执行通过：5条精确DDR复位约束，127对端点；34,403条网络、器件放置及FILETABLE不变。原生阶段及回读222.822秒，输入无漂移。新ADF SHA256为`777bed47bf6489457f42cda54a3cadc4e74f7a4ae2c8caacc51eb49f14e48904`，回执SHA为`b72a6a0a5bed4974e57111a2f471850a0308f9bf635ec9ccf80eb3213e24dc4c`。应用成功不代表时序和例外效果已验收。
- 新`camera720_stage_fast.py`的bootstrap调用冻结完整recipe一次，返回真实验证结果后才封存462项输入。`inspection-seed-a.json` SHA为`f3486b4bfd1999821bca836a2fcf02d52576595b0bb10a6514f918025196f063`；后续同ADF查询逐项重核全部输入、工具和原生脚本，不重复解析历史大报告。新工具38项CPU测试通过，不改冻结原工具。
- `reset-export-a`计划SHA为`92bd19d40b4fe1c18824ee44018a67da003eb98320cbff4c9ce95c7a27f3bab4`，独立PDS重新STA/导出已通过，138.781秒、输入不变。回执SHA为`e720dc4717e3bada13671cabb0e0c87203116bbf0e281375c9fca10d20a00661`。
- 首次完整`audit_camera720_reset_effect.py`实际执行通过，`reset-effect-a.json` SHA为`16bed69e7f3a16f59d48c5ed7356d8eb7c57c8b6be126da2ff91901809174df5`，506项输入绑定。双角十类内部检查全零失败；slow setup/hold/recovery/removal/MPW为+0.148/+0.061/+3.054/+0.399/+0.035ns，fast为+3.143/+0.020/+4.836/+0.059/+0.035ns。每角仅recovery/removal各移除证明范围内245项，数据false-path为0，其余时序行和16类其他例外完全不变；功能图、FF位置及34,403条网络一致。
- 新位流/SRAM工具54项CPU测试通过，额外3项下载前故障注入通过；仅易失SRAM，实际下载仍须通知并取得新的上电确认。新IO证据工具20项CPU测试通过；最终候选原生查询和实际审核待执行。

`io-native-a`的10条单独DVP查询触及300秒上限，回执失败（Elapsed313.093、TimedOut=true、Cleanup.Complete=false）。原生进程稍后自然结束，日志晚于失败回执继续更新；原记录保留，不能用于验收，也不能将后写日志改成该次通过。后续检查未见PDS进程后才启动新候选查询。

`io-native-b`将相同10个源/目标集合并成一次有明确端点列表的查询，已实际通过，87.335秒、输入不变；回执SHA为`3f869fe38408a9b365d91800c9d0551d890a9ae79b709f0648cbd716f6582024`。对回执绑定的报告使用冻结IO纯解析器检查，10端口×双角×setup/hold共40项均有结果、无负slack；完整IO审计仍待final site/route-dump回执，不能从这一步推断外部AC已通过。

`cdc-batch-final-a`已实际完成最终ADF的完整CPU结构重绑定：486项输入，601对路径、2404个必需检查，计划SHA`3ccd658fe0c06c9eaf369b08f22decbb07d7facfd2a7977e669e2b3c2dbab31b`。实际PDS的`report_path_timing`每条会重新初始化子工具，因此原133条timing命令不适合300秒阶段上限。正在新增独立分组适配器，保留明确601对/2404项逐项coverage，减少重复启动；不改原冻结v1工具或把缺项当通过。

## 当前CDC关口：必须修正packed物理端点

**暂停旧601对清单的所有后续原生批次，不将旧结构枚举当作实际物理端点验收。** `cdc-native-g0`的5条分组查询触300秒限制，失败回执保留（Elapsed313.922）；准备的`cdc-native-g1..g3`未执行。后来按每批4条生成的`cdc-grouped-final-b`（SHA`ee2acc4e450a1744bdd30d7c191d0efa3e85acf870fc238ee83d68bc5bea0da0`）及`cdc-native-h0..h4`也仅准备，现均暂停，不执行。

对g0失败运行已写出的报告做只读解析发现仅4个case与旧清单匹配。关键原因：旧清单把packed父实例的`/D`当作原生可查询端点，实际PDS报告落在父实例`/I0`、`/I3`、`/I4`等；无效`-to`可能被Flow静默丢弃，报告header仅剩`-from`。失败g0报告只作诊断，绝不作为通过证据。

进一步独立检查发现同一pack的FF3与FFAPP3不能混淆。`camera_configuration/monitor/request_sync[0]/opit_0_L6Q_LUT6DQL5Q_perm`的主FF3接LUT Z，精确支持包含reset与snapshot_request；FFAPP3接Z5，支持edge_binary[4]/[3]。实际route CONNECT证明snapshot_request从`edge_meta[1]/.../L5Q`到该pack的`I4`；`I0`属于另一寄存器的数据锥，不能拿来证明request_sync[0]。

新独立CPU映射工具`camera720_native_endpoints.py`已完成，13项回归测试通过且root复跑通过。工具SHA`1a40e86a663b22446336ea86eecf2dd5a1e4c5d4116f46630add193b851b1235`；最终清单`native-endpoints-d.json` SHA`eaec79611cbee64e04253f0e3c3f2c62e5fbd5f97947d9f3d67c1283111ce319`。它保留exact source FF/Q和target FF/D|CE|SR，从实际LUT输出依赖、可达性及route CONNECT导出所有native boundary pin，完成124个native INIT一致绑定。完整再生旧601对，展开976个逻辑FF关系到1616个带launch output身份的要求；971个CLK/endpoint对中645个含两个不同launch。另保留60个same-BLE同步级结构关系，不将它们伪装为新增原生查询通过。root已重核28项输入SHA无漂移，976关系全部被新清单引用；独立审阅正在进行。

`packed-native-a`仅准备未执行，是旧I0探针。`packed-native-b`已实际执行，199.157秒、exit=0、输入不变，计划SHA`78af76e1dd9b1779552acbbb1f6783d465028c7c71b0bb5834ce5d20ebc5092f`。小范围get_pins各完整列出14个pin；`CLK→I4`报告保留双端过滤，数据路径的tco明确来自L5Q，slow/fast最大延迟slack分别+7.199/+7.537ns。`L5Q→I4`虽流程退出成功，却明确报告`STA-3005 ... not a valid startpoint`且没有路径；不能把执行成功当作查询有效或时序通过。后续须从CLK查询并核对每条路径实际launch output，不能从L5Q直接查询。该探针尚未给出min路径，正在核实其原因，不算完整CDC验收。未访问板卡。

厂商2023.2-SP3现成help与Tcl手册不支持用`mpnr_report_timing -from/-to`替换Flow查询；`get_path_delay`只给延迟，不能替代setup/hold/exception核验。`query-a`的广泛get_pins虽匹配7834对象，却只打印1000条，不足以证明某内部pin存在或不存在。详见本机`work/camera720-native-query-help-note.md`。

厂商PDS用户手册物理页218明确：`set_max_delay -datapath_only`抑制同路径hold分析。手册SHA`4b49b329809fa5dd4998213e715c2996c92cba26fbed74a8b9f43cb711943bb1`；实测packed-native-b每角max一条、min无条，与同版io-native-b每角17条min形成对照。新CDC收集器按实际约束语义：1515个跨域要求仅核验双角max并明确`HoldAnalysisSuppressed`/`MinDelayNotAccepted`，101个同域同步级仍要求双角setup/hold，共3434适用case。原6464为旧要求数，原件保留，绝不将缺min称为通过。详见本机`work/camera720-datapath-only-note.md`。没有修改FDC或候选ADF。

最终IO site/dump查询`io-sites-native-a`已实际通过，80.640秒、exit0、输入无漂移；计划SHA`86e18288cb64f9ac1ca5ce003dd1dcbac8b75319a74d08057af6d71aadca130d`。完整`camera720_io_fast.py`实际审计也已通过：`io-proof-fast-a.json` SHA`792d12eb8fec8d4689ed4ab5a5cc788dae379729dc042b95bc14233a0830f31e`，527项输入重核无漂移。128引脚/实际site/电气实例、8个输入delay、40/40 DVP case、56 TX最大路径和49条原厂命令齐全。外部AC、TX最小延迟、真实时钟/fps、板电压仍未验收，不能称为实板通过。

独立审阅发现旧60条same-BLE排除中，57条为真正direct Q→D，另3条经LUT并有原生L5Q→I接线，须补查。新增`camera720_cdc_sameble.py`（SHA`d3fc500069a68c3cf5cb3859d851000d63ec22a9ea84184b77052282ec562896`）从实际图/CONNECT逐条导出，10项测试通过；`sameble-supplement-a.json` SHA`e79c699eac4ec835ca090d6099914b86c534e91f2ecb89d0b9dd167f83ceccdf`。因此适用CDC总数修正为3446（不是3434），旧端点清单保留不改。

这3条补充同步级已实际执行`interstage-native-a`，138.829秒、exit0、输入无漂移，回执SHA`9350f1980ae149785d6482943317eff2de81425006ccecaf7bcaea3ebb86c525`。root用冻结普通路径parser独立核验12/12 slow/fast setup/hold，均非例外且tco为对应L5Q，最低hold +0.232ns。逐条结果见本机`work/camera720-output/interstage-local-independent-a.json`。整体CDC仍待新collector和剩余路径补查，不能从这12条推出全体通过。

待执行：新collector复核及实际CDC逐项覆盖→生成并核验测试位流→通知用户上电。已通过的完整内部STA/限定复位效果、最终IO证据及12条补充同步级结果保留。当前尚无720p位流、下载或光学验收。

新collector已完成独立复核与48项相关测试（25 collector、10 same-BLE、13 mapper）。冻结`camera720_cdc_native.py` SHA`26d195148da48e3595272a7dee3fadfbd5f8fda9e9cc39003a08471c67f5a71a`；最终待查计划`cdc-qualified-b/native-plan.json` SHA`8284cb237803073b48e831c8d5c6999a1e6833a2b0160f903020caf5f98ac415`，521项输入/13查询体均独立重核。1619个路径身份对应3446项适用检查，最终export+实际3条补充同步级报告已覆盖463项，2983项缺失、0条记录验证错误；剩余分成38条原生timing命令/13个有300秒上限的上下文。当前开始`cdc-qualified-native-00`；执行和全量覆盖完成前不能写成通过。

**首批实际反馈更新：CIN对象存在不等于合法STA终点。** `cdc-qualified-native-00`执行138.647秒、exit0，但其子工具`run.log`报告`C: STA-3006 .../CIN is not a valid endpoint`。首组frame_age的15个内部CIN被拒，4/8/12/16/20等CLM边界CIN可以报告；不能把同一CLM的边界CIN未经证明地替代所有内部捕获FF。已暂停其余含CIN的批次01–07，正在查真实时序边界映射。冻结executor只拦截E/F诊断，冻结collector的get_pins检查不能发现这种C级STA错误，故`ExecutionPassed=true`或`InvalidPins=[]`均不代表全部端点有效。

`cdc-qualified-check-00/coverage.json`实际部分审核为658/3446覆盖、2788缺失（SHA`7a7538da50530ca1f6c6b560443411d95c3a2bdef3b0bcd308af26bc4c5c12e2`），整体明确false；原始回执/报告不改写。后续需新显式合同处理C级无效endpoint诊断及CLM边界；原B的remaining文本不是已授权的新查询。独立普通同步级批次08–12不含CIN，可继续按B执行并逐份检查原生诊断；当前08开始。

普通同步级进展：`cdc-qualified-native-08`实际138.176秒通过，72/72本组case、无引脚缺失/解析违规/STA-3005/3006；`...-09`实际136.429秒通过，56/56本组case，回执SHA`0b43906ba06ac6adc71e998f3d2f90754e2d95a2b44bd752c205665ed8a4502c`。09完成后root读回脚本误用不存在API，已只修读回并使用原回执，没有重跑09。10–12顺序执行中，仍受每阶段300秒限制。

独立物理CLM映射正在新增helper：内部BLE B/C/D的CIN沿同site、前一BLE COUT和实际CONNECT回溯，直到CLM外部I或BLE A CIN，保留全部逻辑捕获FF及各条局部LUT因果链。初步976关系不变，480关系端点扩展/合并，1616原要求降为1136个真实边界身份（再加3条同BLE补充）；这不等于480条逻辑消费者被删除。尚未声明物理时序聚合已证明。有效CIN12仍有一个packed发射输出缺报告，因此另准备固定from CLK / through L6Q或L5Q / to CIN12的独立只读探针；旧白名单/工具/报告不改。

CLM helper已冻结`camera720_cdc_clm.py` SHA`1aca0f2df5d850fcb300a72c8c243be7985f97c7ada6e0b97af6ad646e25254d`；15新增+13 mapper+10 sameBLE共38项测试root复跑通过。新`physical-clm-boundaries-b.json` SHA`84c66dffc42fa4b84fc32e92dc0a93f38e5d239972096a72634905873f1ddf23`保留976逻辑关系，1136真实边界查询；加3条同步级后979关系/1139查询/2486适用检查。map只证明连线与依赖，不自动接受原生时序聚合，后续收集合同仍需更换。

固定through探针已实际CPU准备/校验完成，独立24测试通过：工具SHA`8218e5b8f9a8f2d7114178d56a197f926b5bd64ca2868978b9c18abc19306355`；`through-native-a/stage-plan.json` SHA`5377579571c3143547827031081a2b031498054ae1fa0acace939a2b03ab1928`，479输入/43工具、300秒、两条精确through L6Q/L5Q查询、独立diagnostic schema。等待普通批次结束才执行，不访问硬件。

普通批次10实际138.166秒、80/80本组case，回执SHA`e82cdddef9af0eb5641a0a20b23f383c948b1d93fd0df623b5282cd9f3fc8181`；11实际138.504秒、76/76本组case，回执SHA`87485fa41c70fd79ea63b1fbbbc35bf9a4208a8af5fdb56874ae56b1b73ead8d`，无C级无效终点诊断、scope/pin/路径检查通过。12执行中。

12实际112.181秒通过，120/120本组case，回执SHA`bad2edc98a2747f3494061ea85f88aa755fa2546d8fb6940ab39d180e2df9909`。全部普通同步级合并baseline+本次有效报告后，104个身份×4共416/416 setup/hold覆盖、0解析违规、0 STA-3005/3006/无效pin诊断；最小setup +6.094ns、hold +0.174ns。root独立摘要`ordinary-independent-a.json` SHA`91d9a103096905a62b2b138e902a3b8a2aa1017f6aa9333fc45be2be564f0b61`，它不是整体CDC签核；完整闭包审核另行生成。`through-native-a`现开始实际执行，仍不访问硬件。

## 暂缓的CI问题

用户截图显示`05c5b19`的push和pull_request两次`Reference and handoff checks`失败，失败步骤为`Check 720p transport preparation and verification logic`。可见报错为`test_camera720_output_prepare.py`中的`ValueError: canonical native PDS shell required`；尾部统计19 failed、158 passed、19 errors、29 subtests passed。两个红叉是两次触发，不能据此认定两种独立根因。

当前工作流使用`ubuntu-latest`，本地此前196项及50子测试是在Windows通过。截图指向测试准备中的路径/环境兼容问题；完整日志及其余失败根因尚未核实，不写成已经确定或修复。不要把本机通过称为远端CI通过，也不要把该测试准备错误称为FPGA实板失败。

用户明确“**不急着解决，继续推进**”：记录问题、继续720p物理主线，本轮不为消除红叉而改冻结构建工具或跳过测试。后续单独修复测试环境兼容并取得CI实际通过结果。

## 最新实测：同域完成，through定位成功

普通链完整输入闭包审核已完成：`cdc-qualified-check-ordinary-a/coverage.json` SHA`0d05852a3e609e46c4e03c85bb38470e4a868d7df092b82ca171c63fba7195be`，647项输入、08–12的92个文件和39份日志全部重核；416/416普通case（208 setup、208 hold）齐全，无C/E/F严重诊断、漂移或解析违规。旧3446合同合计750项覆盖、2696缺失，依旧不通过；无效00未计入该审核。

`through-native-a`实际112.818秒完成，`ExecutionPassed=true`、`ProbeObserved=true`、输入无漂移，无诊断或观察失败；回执SHA`f449ee328da1fd59d78a83c1ccc5d1952f5ea2b633c8aba3aeb46bd43d8b404e`。精确from/through/to保留，held_snapshot101的L6Q到frame_age12/CIN双角max余量+5.508/+6.481ns，L5Q为+5.300/+6.371ns。说明必须用实际发射Q限定查询，原CLK组合报告漏掉较快分支不能当作该分支无路径。诊断工具始终不签核整体CDC或硬件。

下一步用独立的新CLM/through收集合同补齐2486项适用检查；冻结旧工具、无效批次和失败回执均保留，不放宽约束。还需核实共享物理时序端点对全部逻辑捕获FF的覆盖语义。尚无720p位流，不访问开发板，上板前另行通知并确认电源。

独立复核已确认采用厂商正常物理STA模型即可收口，无需继续证明其内部实现：手册说明datapath-only包括发射CLK→Q、组合延迟和接收FF setup；官方Tcl示例直接使用packed CIN作为顺序端点。640个合并物理查询的目标FF逐组核对，均共享同一实际site、CK与FF配置，完整逻辑目标未丢失。依据见本机`work/camera720-clm-vendor-sta-acceptance.md`（SHA`53436f1a119b302dd70c7c191f7a1eab2d5f42ac7d9db6e43d28ac5b6478bd58`）和`camera720-clm-vendor-sta-basis.json`（SHA`7507a8262d7fa61ccf2334e05e5d282cc1b005f86f41c607343f8728f193010b`）。最终须全部实际边界case、完整内部STA及逻辑结构覆盖通过；不宣称逐个内部FF独立枚举或内部聚合公式已证明。

新物理CLM/through收集器已冻结：`camera720_cdc_clm_native.py` SHA`e64b024c8b1c9eeaa7b7b21ef16291e61e5fa534b8a5408551a969b5193a4921`。root复跑14 collector+33位流适配测试通过，独立审查通过。a计划保留为元数据绑定补强前历史，不执行；实际B计划`cdc-clm-through-b/plan.json` SHA`3e5b7fe56b2ced36b29aa5b1a1e8b6e80c494f9a23da3ebd76e94868cab5ee38`，679项输入，已有754/2486项，1732项待补，16条命令分6个300秒上下文。全部缺失身份恰好分组一次，每组每CLK仅选择一个真实Q、最多4个源/64组合，并逐项读回实际tco与三项过滤。严重C/E/F诊断全部拒绝。首批`cdc-clm-native-00`计划SHA`31fdc0476cc8429c2cf219569fd2c1c4a8f732151ae9a27f7dffcd50dd273749`开始执行，其余仅CPU准备。

首批新CLM查询实际141.022秒完成，执行和观察有效、无C/E/F诊断；`cdc-clm-native-00/result.json` SHA`22c78becfb02f9a668a02ad444781d7ee5b96c65cd516d37d452a8cca2a0c229`。但分组只覆盖257/332项，缺75项（held_snapshot104的56项、held_snapshot103的19项），`GroupCoverage.Complete=false`。多源through集合仍被PDS合并较快路径；不能将执行成功当成覆盖完成。初始+该批有效记录合计1011/2486，1475项仍缺。B的01–05仅准备，暂停不执行。

后续收窄到单CLK、单Q、最多28端点的精确查询；共有28个源身份，计划每批4条、最多300秒（由已测2条112.818秒、3条141.022秒估计4条约167秒；实际仍以回执为准）。先跑第一批证明完整覆盖，再继续剩余。已有有效结果全部保留，冻结工具不改，不放宽约束或接受缺项。

方向及模式准备复核：720p的3820/3821=0x41/0x07与已验收VGA正立0x00/0x06的方向位mask0x06完全相同，不会仅因这两个设置回到旧180°倒置。403动作中写入及两次读回验证明确，后续无覆盖；冻结构建副本与当前移植源码一致。取景有实质变化：VGA寄存器窗口2624×1944（y4..1947）、offset16/6；720p窗口2624×1456（y250..1705）、offset16/4，且水平binning位不同。不能直接倍乘VGA K就称720p光学矫正通过。详见本机`work/camera720-orientation-crop-review.md`，传感器6测试及4子测试通过。未修改冻结候选，也未上板。

单源恢复工具`camera720_cdc_single.py`冻结SHA`ca0691fdf60af99a623e1964240e5d4fc6fe4419d97473f6eadd9e6a26157219`；新计划`cdc-clm-single-a/plan.json` SHA`ce557c16859bb163203e17c8a6389520a9109f40972edf10ceff3c5e7754e9ee`，715项输入root重核无漂移，738个缺失路径身份恰好分组一次；28条命令/7个上下文，每条仅一个CLK/Q。首批计划`cdc-clm-single-native-00/stage-plan.json` SHA`23745ada1bde44f41b25bec5d2efdd7d506d7012a2c051ef20cdaa2bd7d63506`已启动，前两条报告各10/10双角case齐全，剩余两条与总回执待完成。其余六批仅CPU准备。

位流适配已支持独立single schema并完整复算其父级和新报告；最终bitstream工具SHA`8d7b7bdf4ed110e9cb573008ff8ca23841094e9a02277514ca4833ab4be81516`。root组合单源/适配/位流/下载相关104项CPU回归通过。9字段请求合同不变，实际完整CDC结果产生前不创建位流授权。

单源首批00实际220.306秒，132/132检查完整通过，回执SHA`83b8412f4cf9ff046b51c5ef7d788298ff233e0b8cb3ce422994c28ae3f637b5`；01实际183.149秒，224/224通过，回执`0a6d6944e1f9081efcd1960df4711cdb1f4cf4d9ee14315a75807ed949d56e5f`；02实际206.931秒，224/224通过，回执`d0683ebbb342976bfce4e8a53a0ba92878deb3aacf3d2021909f0c9158965440`。均输入不变、无C/E/F诊断、scope和实际tco核验有效。03–06正在依次执行，任何执行/观察/覆盖不完整立即停止。当前尚未生成最终完整CDC报告或位流。

首次上板操作与观察单已单独写入[720p首次上板检查](CAMERA_720P_FIRST_BOARD_20261101.md)，并与实际top、预热/LED、输出窗口和SRAM工具独立复核一致。无需HDMI输入；当前top无UART导出，后续原图采集需要独立候选。

单源03实际218.384秒，224/224完整通过，回执SHA`bf5b7f40e04fa4434d334e8036917a87f4c210b5226ba813c8d65408d8b5417e`；04–06继续顺序执行。全量本地Windows CPU回归已完成：31个`test_camera720*.py`文件、530 tests +50 subtests通过，无失败/错误/跳过，125.28秒，源码/工具/清单/测试哈希无漂移；4个原有基线审核也通过。证据位于`work/camera720-windows-regression-20261101-155826-c88db3`，JUnit SHA`9680090e55b8579b5f288a00128309450750ce5541972118718bdf474d8abd1f`。这不是远端CI通过，未修改或跳过CI。

后续光学采图草案见本机`work/camera720-optical-capture-next-note.md`（SHA`652266bbfb62d856dc0957d211d1656d0fec59a8bea214bc0c0165c452917b77`）：当前720 transport无UART exporter；已有PGFRAME1可容纳1843200字节完整原图，921600 UART理想约20秒，但旧raw720包含旧路径、旧复位/输入链和结束heartbeat下载，不能直接复用执行。新采图候选应从已验收raw_delay派生；预览bank只有32768像素，720每四采样57600会回绕，应独立修正或先用诊断图案。先取该模式完整原图与少量几何转移验证，不预先机械要求重拍18姿态。

单源04实际238.246秒，224/224通过，回执SHA`10c0494687e88af5eb7ae390b8a06af575297e620bd173c78efb3e352dcd803f`；05实际284.090秒，224/224通过，回执SHA`4e57f7d69ac7f93f7eef1607b58cd1d16f545b8b993cb9a188db5179d10bf875`。05仍在原300秒上限内，TimedOut=false，未延长上限。最后06正在运行，其余已完成分组无失败/缺项；最终还须完整证据闭包审计，不以简单相加替代。

最后单源06实际280.325秒完成，224/224通过，回执SHA`7f7e29ce10f625695b9f2622d2efc12b90ff382f363f310e7105d91107510dbb`。七批全完成、全部在300秒内、无执行/观察/覆盖失败。root独立轻量合并原始有效记录已得2486/2486、0缺项，其中416同域；同域最小hold +0.174ns，跨域max最小+4.548ns。Get-Process复核未见PDS/fabric/mpnr残留。完整哈希闭包与报告逐项重算现由独立审查执行一次，输出待写`cdc-single-final-a/coverage.json`，其前不创建位流授权。

完整single审核实际完成，663.200秒，`cdc-single-final-a/coverage.json` SHA`d7536f29cf41761da02f721a1417b8d149b536c6ca7ee1a7a6a2448e976bff40`，996项输入无漂移。2486/2486通过、Missing=0、Violations=0：2070跨域max、208普通setup、208普通hold，1139唯一物理查询、979逻辑关系全部保留。slow max/setup/hold最低+4.548/+6.094/+0.274ns，fast为+5.889/+6.805/+0.174ns。厂商物理模型范围内覆盖完整；不宣称内部逐FF独立时序公式、外部AC或实板光学验收。

实际完整结果已写入新`bit-request-a.json`（SHA`7446b33c4015cd160bb13e406501ea9917079c6fd291913364f3c50daab3305c`），绑定最终ADF777bed、effect16bed、IO792d及全部原生回执。root正在执行已测试位流工具的正式CPU authority入口，复用已审计effect/IO三SHA模式，新CDC仍按该工具合同完整复算一次；当前尚未生成bit。完整CDC审计耗时来自约5.1GB输入和逐批重复报告/哈希核验，不是再次运行PDS。

正式位流授权入口实际通过：`bit-authority-a.json` SHA`5c0a3f53742c50df28b67e920d6e59678216e6b4409e197a97771baec1af77f9`，1068项输入/83项工具、最终候选777bed及请求7446b3精确绑定。`FullVerificationCompleted=true`，硬件访问/硬件放行/光学/外部AC均false；这是CPU发布前证明，不是位流或下载。随后开始`bit-a`准备，采用既有位流工具允许的900秒阶段上限（七批查询一直保持300秒）；该阶段必须依序fresh STA→CPU gate→gen_bit_stream，不重新布局布线。

720p位流已实际生成并核验通过：`bit-a/verification.json` SHA`6276dae061048d74950516617793732744052d4530a226f00e4d5328641d2430`；sbit SHA`9affb9b37a269454c437cfe5127fab1dd0c1b35397de6e6f63d486b00bcfe72a`，3,791,112字节，header camera720_transport_top / Logos2-PG2L100H--6-FBG676 / 11/01/26 16:48:58。原生182.882秒、exit0、无诊断/输入漂移，实际事件严格为Report Timing→Runtime gate passed→Generate Bitstream。fresh双角十类时序全过、时钟/summary及所有例外路径保持一致，候选ADF777bed不变。

用户最新明确“已上电，没问题之后可以直接下载，不用再问我”。已在`board-power-authorization-20261101-a.json`记录；本会话检查完成后直接SRAM下载，执行前通知，不重复问许可。正在准备`program-a`，尚未开始JTAG。首次画面仍是720p单位映射传输，光学矫正待下一阶段，Flash不写。

SRAM计划`program-a/plan.json` SHA`f77ae8c04241081e9cce488f33a6ddf4110681236f1b02bc69807aa5a9ed3ac9`已完成独立preflight：1094项输入单次重核无漂移、精确bit9aff/候选777、PG2L100H/0x00602899、JTAG1MHz、scan/program脚本仅SRAM与DONE。复核`work/camera720-program-a-preflight-review.json` SHA`6fc0e10123ae0e80756c3a45809aed446bc6163ea969911573ee82521a0aea7b`。root已通知用户开始下载并启动`camera720_program.py --execute --board-powered --user-notified --timeout-seconds 90`；当前尚待实际回执，不将启动动作称下载成功。

## 实际下载与用户首次720p画面确认

`program-a`已实际完成：2026-11-01北京时间16:55:48–16:57:20，器件PG2L100H/0x00602899、JTAG1MHz，原生program31.3秒，DONE=1。`receipt.json` SHA`57e83bb37a74744cc0ba8ac6176c0bcade53831fba5eb20afe741ea820cb09f5`，Passed=true、DoneConfirmed=true、FlashWritten=false、CleanupErrors=[]，日志哈希全部重核；Get-Process未见PDS/cdt遗留。位流为9affb9...ce72a。

用户随后明确回复“画面正常、方向正确、持续更新”“LED5/6 闪烁，LED7 一直灭”。因此720p传输候选完成首次实屏定性观察，持续采集/处理与无故障灯已确认；未单独确认黑边，不自行补写。原话及本次下载绑定见`live-observation-a.json` SHA`41e85b19f6588b6135195a35c409598f0f98e281b49b5b258c9e6e71bd40bbad`，实时状态`current-live-state.json` SHA`cfd07af87e04522e44192befbe6c069ff54b9f18a93f6c5e8850a5b61d842139`。无逐像素实采、实测PCLK/fps、长期稳定或720p光学矫正结论。

用户追问“矫正畸变没加上是吗？验证还需要拍很多照片吗？”：已明确当前720p为单位映射，尚未加入该模式镜头矫正；VGA矫正及标定数据完整保留。下一步先完成独立720p原图采集候选并取得一张完整原图，验证裁剪/缩放几何转移，可靠时转换原K并用少量独立棋盘图验证；不可靠或验证失败才补标定，不预先要求整套18张重拍。摄像头仍固定在FPGA转接板上，不要求挪动摄像头，右下硬件遮挡事实保留；目前不要求用户摆棋盘。清晰度/该模式矫正完成后才测量并提升帧率。
