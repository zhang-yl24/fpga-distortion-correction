# DDR IP 内部约束集成提案（2026-10-28，仅规划）

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

实际3个IP内部启动寄存器，在最终网表和报告里均存在：

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
5. 任何matched path的source或endpoint在IP外、出现第七个clock pair、出现TX_DATA/D/RAM data endpoint，均拒绝该候选。目标是覆盖表内六组的全部244个检查，而不是只消除slow244/fast233负数。

## 语法依据与未验证点

本机PDS2023文档给出了可用能力，而非“工具不支持精确pin”的障碍：

- `User_Constraint_Editor_User_Guide.pdf`印刷页104附近的set_false_path说明允许`-from/-to`通过get_pins/get_cells取得；get_pins查询在印刷页127，支持`-hierarchical/-regexp`。
- 同手册对象命名说明：后端实例层级使用`/`，instance与pin之间使用`:`；前端对象命名可不同。报告显示的`inst/pin`不能不经核对直接当作后端query字符串。
- `Tcl_Command_User_Guide.pdf`印刷16–17页支持`add_constraint <path>`加载fdc/lcf/scf/pcf/rcf。手册没有替我们证明“fresh map后add FDC就能解析这些final网表名”；下轮必须显式核工具匹配。若map后的对象名与最终PNR不同，应绑定fresh map inventory而不是硬套E最终名字。

以下是**有文档依据、但未在PDS执行验证的单条示例**，展示精确source/endpoint写法；不是可直接加载的完整约束文件：

```tcl
set_false_path -from [get_pins -hierarchical -regexp {^u_ddr3_test_h/u_ddrphy_top/ddrphy_reset_ctrl/ddrphy_dqs_rst/opit_0_inv:CLK$}] -to [get_pins -hierarchical -regexp {^u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_ca_group\[0\]\.u_ddc_ca/ddc_inst:RST$}]
```

生成器必须对所有名字做regex字面转义并加`^...$`，特别是`[0]`、`.`，不能以Tcl大括号替代regex转义。也可用工具验证的完整字面pin列表；不要依赖不明glob对方括号的解释。collection大小及后端冒号格式的实际结果应写回执，不在失败时放宽pattern。

## 下轮原生验收条件

- 报告记录source、to及命中路径对象。只允许表内六个IP内部clock pair；slow/fast各244总检查被原配来源例外覆盖，命令无missing/ambiguous object；不得只有数量相等而端点不同。
- 若exception报告本身仍max_path20截断，完整匹配证明仍未完成；可以把这六组的**报告路径上限**提高到足以列全的数量（不是放宽时序），并核实际枚举。不能以仅54样本或interaction计数替代端点检查。
- `ddrphy_sysclk ↔ phy_dq_sysclk_0/1`真实数据setup/hold保持Timed，包括当前DQ组3、dq_loop[6]的TX_DATA[2]失败端点；不加它到reset名单。
- 自研board27、input_pixel、pixel_clk、cfg_clk、core域之间的检查和8ns/0ns诊断边界保持；不加入free_clk/board27单组，不对全IP实例或全层级做false_path。
- 入口power_ready→rst_seq同步器的1项仍单独报告，不能因例外删除。即使内部244采用官方约束，当前hold、入口RDC及外部IO/CDC仍是独立工程事项。

## 入口1项的独立RDC方案

应按标准异步assert/目标域同步deassert结构实现/保留真实DFF链，并防止被合并为gopSRL2；只在局部可读wrapper内处理启动序列，不把LOCK反馈到整个DDR resetn。原始resetn同时复位启动GPLL，若等该PLL的LOCK才释放它会死锁。目标域释放必须在可用rst_clk和LOCK条件下完成，并验证上电、手动复位、LOCK变化/调相不产生循环或提前训练。对该同步链的精确RDC例外、级间时序与物理结构独立验收，不随官方内部六组自动豁免。

## 工程结论

可以依据适用的原配IP约束继续做集成候选，不必把FAE逐端点解释当作所有开发的前置条件；但本地已有两条明确反证必须保留：全局组会切自研1597条检查，真实数据hold在A/E定向200ps试验后仍未消除。最窄方案是“具体IP source clock pin + 具体IP reset pin”，以实际对象/例外报告验收；不是把IP所有路径或自研边界一起关闭。
