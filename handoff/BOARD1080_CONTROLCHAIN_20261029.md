# ControlChain-off 实验结论（2026-10-29）

**拒绝将本方案选为默认或时序修复。** 原生完整流程退出0，但关闭ControlChain后出现另一条更差的hold路径；slow/fast最差hold从E的−0.037/−0.222ns变为−0.205/−0.802ns，recovery仍245/234项失败。不能称为全内部通过。

## 本轮身份

- 工作目录：`distortion/build/board1080-timing/ccoff-1029-a/`。
- 真实退出0，用时765.31s，执行回执InputDrift为空；stdout无E:。无位流生成或硬件访问。
- curated回执：`distortion/results/board1080-controlchain-20261029.json`。原始XML411,335,827字节，用iterparse提取必要表；不提交或复制巨型报告、sim.v正文。
- 109项原始manifest闭包与A/E一致，当前原件及109项编译副本重核无漂移；5个编译副本仅include绝对路径因输出目录不同。113项计划输入除helper哈希外不变，原FDC/RCF及clock定义保持原样，没有加载窄scope候选约束。
- 额外动作只有只读map pin-query、将报告max_path调为300、STA后执行gen_netlist功能网表导出。导出成功不等于已执行网表仿真。

## 选项确实进入route阶段

实际PNR命令为：

```tcl
pnr -optimize_multi_corner_timing -fix_hold_violation -share_router_control_signal FALSE
```

stdout有原生successfully；生成工程的`cmd_route`完成状态中保存`share_router_control_signal FALSE`，不是只在未执行的准备文件里写了该值。run_route.log未单独打印此布尔值，应组合读取原生命令与route配置证据。

本机原生help对该选项的说明仅为“Reduce CE/RS signal”。不能据此预设它直接控制CR1/CR3的数据路径；下述是实际同端点时序差异，而不是超出文档的机制结论。

## 十类结果及A/E对照

| 检查 | A/E slow | ControlChain-off slow | A/E fast | ControlChain-off fast |
| --- | --- | --- | --- | --- |
| setup | 0失败 +0.447ns | 0失败 +0.642ns | 0失败 +3.248ns | 0失败 +3.131ns |
| hold | 1失败 −0.037ns | 1失败 −0.205ns | 1失败 −0.222ns | 1失败 −0.802ns |
| recovery | 245失败 −4.056ns | 245失败 −4.055ns | 234失败 −3.023ns | 234失败 −3.021ns |
| removal | 0失败 +0.353ns | 0失败 +0.354ns | 0失败 +0.160ns | 0失败 +0.159ns |
| MPW | 0失败 +0.035ns | 0失败 +0.035ns | 0失败 +0.035ns | 0失败 +0.035ns |

A与E的十表原本完全相同；E还包含一次显式200ps后置hold优化，本ControlChain实验没有启用该后置选项，故不能伪装为仅“在E基础上切一个布尔值”的严格单变量优化收益。实际对照仍足以否决当前方案：完整时序没有通过，hold反而更差。

## Hold究竟是哪条路径变坏

新最差为：

- 起点：`u_ddr3_test_h/u_ddrphy_top/ddrphy_reset_ctrl/training_error_latch/opit_0_inv_L6Q_perm/CLK`。
- 终点：`u_ddr3_test_h/u_ddrphy_top/u_ips2l_ddrphy_rst_clk_phase_adj/rst_clk_adj_start_d[0]/opit_0_srl/D`。
- 时钟：`rst_clk → ddrphy_sysclk`；无exception；检查的是D数据端，不能混称为纯reset pin。

与E中**完全相同起终点**比较：

| 量(ns) | E slow | 本轮 slow | E fast | 本轮 fast |
| --- | ---: | ---: | ---: | ---: |
| hold slack | +1.169 | −0.205 | +0.119 | −0.802 |
| data delay | 2.983 | 1.609 | 2.012 | 1.091 |
| logic delay | 0.158 | 0.517 | 0.103 | 0.335 |
| route delay | 2.825 | 1.092 | 1.909 | 0.756 |
| clock skew | +1.721 | +1.721 | +1.817 | +1.817 |

slow时布线减少1.733ns、逻辑增加0.359ns，合计数据延迟减少1.374ns，hold裕量也减少1.374ns；fast时布线减少1.153ns、逻辑增加0.232ns，合计数据延迟及裕量减少0.921ns。时钟偏差和起止时钟延迟未变。缩短数据路径会伤害这条hold，不能把更短布线一概当改善。

原A/E最差端点是DQ组3 `dq_loop[6].u_iobuf_dq/opit_1/TX_DATA[2]`（core→phy_dq_sysclk_1），与当前新最差不同。当前原生该clock pair汇总已无hold失败；它的改善没有抵消新路径失败。

## Recovery、资源与覆盖

PHY六组+入口的失败数量没有减少：slow245=244PHY+1入口，fast234=233PHY+1入口，fast少11项仍是rst→phy_div0组35项中的11项非负。max_path300下实际详细行数和唯一端点计数见JSON，不把不同时钟/工艺角检查相加成独立FF。

资源仍为14,572 LUT、19,339 FF、610 distributed RAM、78 APM、17.5 DRM(36K等效)、134 IO。11个时钟仍有5个无同域setup/hold观测，no_input_delay54、no_output_delay110；board27→rst_clk的Timed(unsafe)仍在。无新增宽async/false-path排除。

## 只读查询与导出边界

map查询原件`pin-probe.txt`记录：`PDS_PIN_RAW @tcicmdresult36`、Tcl list length=1、ITEM仍为同一句柄。这不能证明匹配了一个pin，也未验证canonical名称；本轮没有据此加载任何scope例外。后续MPNR例外实验属于另一项工作，不混入本ControlChain结论。

`gen_netlist -force_to_run -func_sim_only`实际成功生成30,943,106字节的功能sim.v，回执只存路径/哈希，不复制正文。它为后续工程分析提供材料，不是新的数字仿真PASS或硬件证明。

## 快照与文件保留

最终ADF SHA256 `f4dfa5d14c494a880d4ea17d7a8cb1befa2c3c6e7d8f5535d47546ff8fbb6b29`；快照SHA相同。源修改UTC `2026-10-29T02:48:33.624492+00:00`，快照创建UTC `2026-10-29T02:48:35.771103+00:00`，STA engine日志创建UTC `2026-10-29T02:48:37.072551+00:00`。已存快照与最终ADF字节一致、创建早于STA engine日志；没有独立外部前STA哈希采样，不扩张这一证据边界。

原报告、计划、执行回执和A/E失败证据均保留。此选项保持非默认；不改RTL/FDC或正式门禁，不以本次退出0放行。
