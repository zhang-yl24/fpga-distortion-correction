# DDR IP 内部约束集成提案（2026-10-29，候选验证中）

本提案基于 E 最终网表和原生时序报告，不修改正式 FDC/RTL，不执行 EDA，不放行硬件。目标是在保留严格诊断结果的同时，把**同配置 IP 配套约束作为 IP 设计依据**，建立只覆盖 IP 内部复位/训练关系的集成候选；不以等待 FAE 逐端点解释作为全部开发的前置条件。

## 设计依据与范围

- 当前 IP 与随板示例的 IDF/371 参数及 74 个综合源字节一致，PG2L100H-6/FBG676、x32/BANK_NUM2、ref125MHz/DFI8ns 相符。配套 FDC 可以作为这部分 IP 的设计约定，不能一概称为无依据豁免。
- 实际工具为 PDS2023.2-SP3，IP 来自2022.2-SP6.4。官方示例在本机也存在真实 hold 失败。因此“采用原配约束”不等于自动证明所有时序或所有工具版本兼容；真实数据 setup/hold 仍需通过。
- 原始五条 `set_clock_groups ... -group [get_clocks {...}]` 都是单组全局命令。原官方 XML 除六组244项外，还切除 free→core569、core→free65、free→rst8、core→rst5、rst→core43、phy_div0→rst1 等检查。不能只把 free_clk 重命名为 board27 后整体复制。
- A/E 的 board27 跨域汇总检查有 input→board376、board→input532、board→core679、core→board3、board→cfg1、cfg→board2、board→pixel3、board→rst1，合计1597。全局 board27 组会额外切自研 CDC；即使不加 board27 组，rst_clk 单组也会把外层 power_ready→IP入口切掉。两者均不采用。

## 本次允许的六个关系

| Launch → Capture | 总检查数/角 | E slow 失败 | E fast 失败 |
| --- | ---: | ---: | ---: |
| rst_clk → phy_dq_clk_0 | 34 | 34 | 34 |
| ddrphy_sysclk → phy_dq_clk_0 | 3 | 3 | 3 |
| rst_clk → phy_dq_sysclk_0 | 35 | 35 | 24 |
| rst_clk → phy_dq_clk_1 | 84 | 84 | 84 |
| ddrphy_sysclk → phy_dq_clk_1 | 4 | 4 | 4 |
| rst_clk → phy_dq_sysclk_1 | 84 | 84 | 84 |
| **PHY 合计** | **244** | **244** | **233** |

这244是每角的检查数，不是244个物理引脚或FF；fast少11个失败是同一35项中11项已非负，不是删除。入口 board27→rst_clk 的1项不在表中。

原始证据：`distortion/build/board1080-timing/holdfix-full-20261028-e/report_timing/rtr.db`；A/E原生十表逐项相同。按max_path20报告的每角88行负样本只有54个唯一End Point，不能从该样本复制出“完整244端点白名单”。

## 2026-10-29完整原生路径更新

`distortion/build/ddr-fix-20261029/mpnr-base-g/board1080_top.rtr` 已提供六组全部recovery路径：slow/fast每角各244条，逐项计数均为34/3/35/84/4/84，且两个角的source/endpoint、launch/capture及边沿身份集合完全相同。fast的11条非负检查均保留（0.009至0.173ns），不是只从负slack样本选端点。配套 `board1080_top_exception.rtr` 的八个false_path类型/角section均无例外路径。原生路径和summary计数、失败数已交叉核对。

完整证据见 `distortion/results/board1080-native-recovery-20261029.json`，由独立CPU工具 `distortion/tools/prepare_ddr_native_recovery_constraints.py` 生成，绑定两个原生report的SHA。每角244检查去重后有126对精确source/endpoint；其中原首版三个source仅占125对、243检查：dqs_rst为104对/208检查（RST7、ISR32、OSR65），iol_rst为14对/28检查，training_rstn为7对/7检查。不能把158个候选pin存在对象都写成已命中检查；实际未检查的33个ISR pin不进入此候选。

新增的一对是 `ddrphy_cpd_ctrl/ddrphy_cpd_rstn/opit_0_inv_L6Q_LUT6DQL5Q_perm/CLK` → `u_ddrphy_cpd/cpd_inst/RST`（完整前缀为 `u_ddr3_test_h/u_ddrphy_top/`），属于rst_clk→phy_dq_sysclk_0，slow−0.665ns、fast+0.067ns。它在IP内部，但超出首版三个source和slice目标范围，**当前候选明确排除CPD，不能宣称覆盖244**；只有这项经过单独原厂/连通性依据核验后才能另加。

已生成但未应用的 `distortion/build/ddr-fix-20261029/native-recovery-candidate.fdc` 只包含上述125对，以完整原生slash pin名分别绑定source和endpoint，不作笛卡尔积，不包含CPD、board27入口或任何数据pin。每个查询均采用字面转义且首尾锚定的regex，collection大小必须等于1，否则报错；不回退为clock group、层级通配或无时序pin。独立探针仍须确认当前数据库对象名、约束加载和原生exception路径，243条候选coverage不能提前写成已应用或时序通过。生成器的12项CPU测试覆盖真实完整report、非负路径缺失、重复/异角替换、错误family/data endpoint和已有false_path基线等反例。

以下E inventory及首版方法保留作为历史设计依据；新的实际受检端点以本节完整原生报告为准。此前文档中的后端冒号pin示例不作为本机约束加载的证据；当前候选使用原生report的完整slash名称，后续以工具probe实际返回为准。

## E 最终网表的实际对象 inventory

来源：`holdfix-full-20261028-e/place_route/board1080_top_route_optimize.netlist`。该文件列出 Inst/Pin 的名字、原语类型、pin方向，**没有逐网 driver/load 连接表**。因此以下是对象存在清单，不冒充完整连通性或全部检查匹配证明。

仅在 `u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/` 下查五类reset pin：

| 原语 | 实例数 | 已列出相关 pin | pin存在数 |
| --- | ---: | --- | ---: |
| gopDDRPHY | 4 | RST、RST_TRAINING_N | 8 |
| gopDQSL | 3 | RST、RST_TRAINING_N | 6 |
| gopTSERDES | 14 | TSR | 14 |
| gopIOL | 65 | ISR_IOLHR、OSR_IOLHR | 130 |
| gopDDRPHY_IOCLKDIV | 2 | RST | 2 |
| gopPPLL | 2 | RST | 2 |
| **原始候选** | **90** | RST11 / TRAINING7 / TSR14 / ISR65 / OSR65 | **162** |

**首版排除 PPLL 两个 RST 和 IOCLKDIV 两个 RST**：它们不是已报告的六组失败样本，不能因为同名RST就顺手覆盖。余下可枚举158个pin存在对象，分为普通DDRPHY/DQSL RST7、IOL reset130、TSR14、训练reset7。某些IOL pin可以未接、接常量或没有对应STA检查；158不是244，也不能靠这个数量猜测全匹配。

首版枚举的3个IP内部启动寄存器，在最终网表和报告里均存在（不包含上节新发现的CPD source）：

1. `u_ddr3_test_h/u_ddrphy_top/ddrphy_reset_ctrl/ddrphy_dqs_rst/opit_0_inv`：gopQ，存在CLK、Q，来源时钟rst_clk。
2. `u_ddr3_test_h/u_ddrphy_top/ddrphy_reset_ctrl/ddrphy_iol_rst/opit_0_inv_L6Q_LUT6DL5Q_perm`：gopLUT6L5Q，存在CLK、L5Q，来源时钟rst_clk。
3. `u_ddr3_test_h/u_ddrphy_top/ddrphy_training_ctrl/ddrphy_dqs_training_rstn/opit_0_inv_L6Q_LUT6DL5Q_perm`：gopLUT6L5Q，存在CLK、L5Q，来源时钟ddrphy_sysclk。

报告中的真实Start Point使用上述实例的`/CLK`，不是全局时钟集合。7个训练endpoint已完整出现：CA组0/1/2的`u_ddc_ca/ddc_inst/RST_TRAINING_N`以及DQ组0/1/2/3的`u_ddc_dq/ddc_inst_PHY/RST_TRAINING_N`，路径前缀均在IP内部。

## 可执行生成方法

下一轮先做生成器和CPU验收，再在独立完整流程中应用；本轮不再做第三次完整PNR。

1. 解析fresh map后可读网表的Inst/Pin记录，要求3个source clock pin均唯一；按原语类型和**完整IP前缀**枚举上述目标，不用`*RST*`全工程通配。训练7个、TSR14个、普通RST7个、IOL候选130个的对象清单及来源网表SHA写入plan。
2. 对3个source分别生成约束：dqs_rst只允许到DDRPHY/DQSL的RST及IOL的ISR/OSR，iol_rst只允许到14个TSR，training_rstn只允许到7个RST_TRAINING_N。优先使用实际连通性精简目标；若只能取得pin存在清单，必须明确这些是查询候选，并靠工具原生异常报告验收实际路径，不能先宣称它们全部有效。
3. `-from`使用具体的IP寄存器clock pin（或对应唯一时序cell），不用`get_clocks rst_clk/ddrphy_sysclk`。`-to`为完整命名、字面匹配的硬原语reset pin，全部在IP内部。每条约束均同时绑定source与endpoint，从而不会切掉这些目标其他来源的路径。
4. 新FDC只在dev_map后加入，并保留原诊断FDC、原RCF、原时钟、原多周期约束不变。map后对象若匹配为空或歧义，立即报错；不能回退成clock-group。此阶段加载精确物理名在本机**尚未实际验证**，不能保证加入后一定解析成功；需以PDS约束检查和exception报告为准。
5. 任何matched path的source或endpoint在IP外、出现第七个clock pair、出现TX_DATA/D/RAM data endpoint，均拒绝该候选。完整目标覆盖表内六组244个检查；当前三source候选因独立保留CPD只覆盖243个，不靠删除fast非负路径改变目标。

## 语法依据与未验证点

本机PDS2023文档给出了可用能力，而非“工具不支持精确pin”的障碍：

- `User_Constraint_Editor_User_Guide.pdf`印刷页104附近的set_false_path说明允许`-from/-to`通过get_pins/get_cells取得；get_pins查询在印刷页127，支持`-hierarchical/-regexp`。
- 同手册对象命名说明：后端实例层级使用`/`，instance与pin之间使用`:`；前端对象命名可不同。报告显示的`inst/pin`不能不经核对直接当作后端query字符串。
- `Tcl_Command_User_Guide.pdf`印刷16–17页支持`add_constraint <path>`加载fdc/lcf/scf/pcf/rcf。手册没有替我们证明“fresh map后add FDC就能解析这些final网表名”；下轮必须显式核工具匹配。若map后的对象名与最终PNR不同，应绑定fresh map inventory而不是硬套E最终名字。

以下是当前完整原生slash名称的单条示例，展示精确source/endpoint写法；实际加载仍须probe验证，不是可直接加载的完整约束文件：

```tcl
set_false_path -from [get_pins -hierarchical -regexp {^u_ddr3_test_h/u_ddrphy_top/ddrphy_reset_ctrl/ddrphy_dqs_rst/opit_0_inv/CLK$}] -to [get_pins -hierarchical -regexp {^u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_ca_group\[0\]\.u_ddc_ca/ddc_inst/RST$}]
```

生成器必须对所有名字做regex字面转义并加`^...$`，特别是`[0]`、`.`，不能以Tcl大括号替代regex转义。也可用工具验证的完整字面pin列表；不要依赖不明glob对方括号的解释。collection大小及实际后端完整pin名应写回执，不在失败时放宽pattern。

## 下轮原生验收条件

- 报告记录source、to及命中路径对象。只允许表内六个IP内部clock pair；slow/fast各244总检查被原配来源例外覆盖，命令无missing/ambiguous object；不得只有数量相等而端点不同。
- 若exception报告本身仍max_path20截断，完整匹配证明仍未完成；可以把这六组的**报告路径上限**提高到足以列全的数量（不是放宽时序），并核实际枚举。不能以仅54样本或interaction计数替代端点检查。
- `ddrphy_sysclk ↔ phy_dq_sysclk_0/1`真实数据setup/hold保持Timed，包括当前DQ组3、dq_loop[6]的TX_DATA[2]失败端点；不加它到reset名单。
- 自研board27、input_pixel、pixel_clk、cfg_clk、core域之间的检查和8ns/0ns诊断边界保持；不加入free_clk/board27单组，不对全IP实例或全层级做false_path。
- 入口power_ready→rst_seq同步器的1项保留原始检查记录，并按下节独立验证、记录RDC例外；不能由内部六组规则自动覆盖。即使内部244采用官方约束，当前hold、入口RDC及外部IO/CDC仍是独立工程事项。

## 入口1项的独立RDC方案

2026-10-29复核建议保留原IP同步器，按独立、精确的入口RDC处理；现有证据没有证明需要修改IP或禁止gopSRL2 packing。

可读generated wrapper `distortion/platform/video_base/ipcore/ddr3_test/ddr3_test_ddrphy_top.v` 的 `u_ddrphy_rst_seq_rstn_sync` 以 `rst_clk` 为时钟、`ddr_rstn` 为异步复位、`rst_gpll_lock` 为输入，输出 `rst_seq_rstn`。E的 `synthesize/board1080_top_syn.vm` 中对应模块为两个 `GTP_DFF_C`：同一异步clear、同一时钟，D按LOCK→FF1→FF2串接，输出取FF2。它是带异步初始化的LOCK两级同步器；共享raw reset符合通常的异步assert/同步释放结构，本身不是结构反证。PDS公开 `arch/vendor/pango/verilog/simulation/GTP_DFF_C.v` 确认其clear为异步置0。

E原始入口检查为 `power_ready/opit_0_inv_L6Q_perm/CLK` → `u_ddr3_test_h/u_ddrphy_top/u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/opit_0_srl/RS`，slow/fast slack分别为−3.308/−1.962ns。它按board27与rst_clk的边沿关系检查raw reset释放，负值不能单独证明同步器输出会提前释放。标准两级复位同步器也需要将其异步clear入口与下游正常时序检查区分；可参考[AMD UG906的异步复位同步器说明](https://docs.amd.com/r/2022.1-English/ug906-vivado-design-analysis/Asynchronous-Reset-Synchronizer)。这项入口例外以同步结构为依据单独记录，不冒充内部六组244项的配套约束。

2026-10-29的 `ccoff-1029-a` 完整PNR后已通过官方 `gen_netlist -force_to_run -func_sim_only` 导出 `generate_netlist/board1080_top_sim.v`（30,943,106字节，SHA256 `1ccb8f9e90362319064b6db51e88882043b3cdac2331e853326f7b1d99d88113`）。此候选中gopSRL2实际展开为同一CLMA_357_745的两个 `V_FFASYN`，均为 `GRS_EN="TRUE"`、`SET_RESET="RESET"`、`LRS_EN="TRUE"`、`INIT=0`、`CE=1`，同一rst_clk缓冲时钟。连接为启动PLL的LOCK→FF3.D→FF3.Q→FFAPP3.D→rst_seq_rstn；FF1只有FF2一个功能负载，FF2的14个直接负载均在IP的ddrphy_reset_ctrl内。两个SR与启动PLL的RST接同一LUT，其实际真值表为 `~(reset_n & power_ready)`，没有LOCK反馈到PLL reset。共享SR/CK及同位置packing没有破坏这两个寄存器级。

结构记录见 `distortion/results/board1080-entry-rdc-20261029.json`，由只读CPU工具 `distortion/tools/audit_ddr_entry_reset_netlist.py` 对实际官方公开网表生成；工具解析38,749个primitive cell，拒绝不符格式、重复对象/端口、额外驱动或扇出、关键网上的隐藏assign、错误CE/clear/INIT/clock以及raw reset的LOCK依赖。对应17项CPU测试通过，包括本机真实导出及定向负例。此证据确认当前候选的功能连接；不等于测得模拟亚稳态MTBF、硬件稳定性或已应用时序例外。

此前E的 `.netlist` 只列出对象/引脚，fresh map直接导出也曾返回 `Flow-0044: Place hasn't been run`，均不能代替这次PNR后的官方网表。PDS公开 `verilog/bsim/V_FFASYN.v` 定义异步SR和recovery/removal检查；指定的 `gopSRL2.eval`、`devSRL2.eval` 为PANG二进制容器，未解码、不作为可读映射证据。以后变更RTL、IP、工具或构建选项仍应对新的实际导出重跑审计，不能沿用旧候选SHA的结论。

候选入口例外仅绑定fresh inventory中唯一的power_ready源clock pin与上述同步器唯一RS pin，使用完整字面名/转义后的锚定regex并检查collection数量；不使用整个board27/rst_clk时钟组，不匹配全IP reset。外部手动reset若有需处理的检查，单独核对真实来源与同一同步入口后记录。保留LOCK数据入口、两级之间的等效时序及FF2到下游的正常检查，并在工具回执中区分原始检查、入口RDC例外与内部六组例外。最终物理名字变化或导出显示结构不符时应停止应用该条候选并重新检查，不能放宽范围。

`hardware_check/ads-synthesis.txt` 的 `syn_srlstyle="registers"` 只规定inferred shift register综合为寄存器，`syn_preserve` 只规定综合保留寄存器；两者都未承诺阻止后端packing。增加第三级也不能保证拆除gopSRL2或自动消除异步reset检查。因此不把某属性、级数或macro名字作为结构验收替代。

定向验证覆盖无时钟时异步复位、LOCK为0时释放raw reset、相对rst_clk的释放相位扫描、LOCK上升/下降、调相期间LOCK变化及再次复位，检查rst_seq_rstn保持原厂两级采样语义、训练不提前且能恢复。RTL仿真不能证明模拟亚稳态MTBF，需结合实际映射结构和保留的时序检查验收。不把LOCK反馈到整个DDR resetn：原始resetn直接复位启动GPLL，等待其LOCK再释放它会死锁；修改LOCK处理也可能破坏原厂动态调相流程。

## 工程结论

可以依据适用的原配IP约束继续做集成候选，不必把FAE逐端点解释当作所有开发的前置条件；但本地已有两条明确反证必须保留：全局组会切自研1597条检查，真实数据hold在A/E定向200ps试验后仍未消除。最窄方案是“具体IP source clock pin + 具体IP reset pin”，以实际对象/例外报告验收；不是把IP所有路径或自研边界一起关闭。
