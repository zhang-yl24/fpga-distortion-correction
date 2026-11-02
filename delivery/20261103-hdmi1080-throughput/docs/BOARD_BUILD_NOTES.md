# HDMI 1080p 完整板级候选构建

`tools/build_board_candidate.py` 为 PDS 2025.2 提供分阶段源码准备、综合/Map、布局布线、双角 STA 和位流生成。它不会调用 JTAG、串口、Flash 或下载命令。每个阶段保留独立工作目录、原始日志、输入数据库及源码哈希；同名阶段目录存在时拒绝重用。

基线为 `delivery/20261103-hdmi1080-demo-source` 中的真实 HDMI 主链，130 项依赖闭包、49 项 `add_design`、`board1080_top`。195ae5a 与随后 2263444 的处理链源码及依赖清单相同。`main` 的摄像头 1080p60 直通工程另有独立 top 和配置，当前工具沿用已演示的 HDMI 29.97/30Hz 校正工程。

## 原先缺少的内容与恢复范围

- 50 项交付源码已经在 Git 中；另外 80 项厂商或派生依赖按 `source-manifest.json` 的字节长度与 SHA256 恢复到外部 `native` 目录，准备脚本逐项校验。构建只使用精确匹配的文件。
- 原始 FDC 有 142 个引脚，当前 top 有 144 个端口，缺少 `telemetry_rx` 与 `telemetry_tx` 两项物理属性。工具新增独立 `uart-pins.fdc`，原 FDC 保持原字节。
- 完整原演示版 PNR 操作序列及最终 PCF/ADF 没有随源码包交付，原始 ADF/bit 仅保留身份哈希。新构建从源码重新 Map，不声称重现同字节位流。
- baseline、cache、both 三版已完成完整 PNR/STA 和诊断位流导出。实际 IO 时序、DDR 复位/CDC 与板测验收仍待完成；[最终证据](../evidence/board/summary.json)记录各版结果。

## UART 物理属性来源

| 当前端口 | 位置 | 电气属性 | 仓库证据 |
|---|---|---|---|
| `telemetry_tx` | C24 | 3.3V、LVCMOS33、4mA、SLOW | `distortion/board/bringup.fdc:11–15` 中的 `uart_txd` |
| `telemetry_rx` | B24 | 3.3V、LVCMOS33、上拉 | `distortion/board/corrected_gamma_d5.fdc:827–833` 中的 `uart_rxd`；注释引用厂商硬件指南 2.1.3.2.5 的 CP2102 UART RX |

overlay 仅加入端口物理/电气属性，没有加入 false path、异步 clock group、multicycle 或放宽时钟。旧 camera FDC 的 UART timing exception 不会复制。准备阶段检查 144 个端口与引脚一一对应且没有位置冲突；Map 和 PNR 后重新检查原生 PCF/引脚报告、方向、IO 标准及同 bank 声明电压。该检查验证设计声明，不等同于测量实物电源轨。

## 使用命令

在完整包的本交付目录执行，Python 3.10+，仅依赖标准库。先设置路径：

```powershell
$flow = 'tools/build_board_candidate.py'
$pds = 'E:/PDS_2025.2-ads-win64/pango/PDS_2025.2-ads/bin/pds_shell.exe'
$native = '../../native-dependencies'
$out = 'D:/fpga-build2'

python -B $flow prepare --dependency-native $native --output-root $out --run-name both-rebuild-01 --variant both --mode corrected
$work = "$out/both-rebuild-01"
python -B $flow run --work $work --stage map --pds-shell $pds
python -B $flow run --work $work --stage route --pds-shell $pds --seed 1 --timeout-seconds 10800
python -B $flow run --work $work --stage sta --pds-shell $pds
```

`baseline/writer/cache/both` 和 `raw/corrected/demo` 均可独立准备。每份配置的 `param_id` 由源码绑定；切换参数或 RTL 时使用新的 run 名。建议先比较 `baseline + corrected` 与 `both + corrected`，cache 用作单项优化对照；both 在本次同条件构建中具有最高的仿真吞吐，slow setup 失败端点为 16，仍需收敛时序和实板验证。

准备目录须保持原位置，源码内的绝对 include 已绑定该目录。选择短输出路径，准备脚本会在写入前检查 240 字符限制；跨电脑使用完整包的重建入口重新生成本机路径。

## PDS 阶段与原生证据

| 阶段 | 操作 | 验证与输出 |
|---|---|---|
| prepare | 校验完整闭包、生成编译副本和 UART overlay | `preparation.json`、`board-flow.json`、完整 144 引脚声明 |
| map | `compile` → `synthesize -ads -selected_syn_tool_opt 2` → `dev_map` | `map-result.json`，原生 Map ADF、PCF、引脚报告、器件/封装检查 |
| route | 从当前 Map ADF 执行 PNR | `route-result.json`，最终 routed ADF 与原生 144 引脚报告 |
| sta | 对同一 routed ADF 执行 `report_timing -delay_type min_max` | `sta-result.json`，Slow/Fast 两角的 setup、hold、recovery、removal、MPW、Skew 全部表格与异常报告 |
| bitstream | 从上述 STA 绑定的同一 ADF 导出 | `bitstream-result.json`、`export/` 中带配置身份和验收状态的 `.sbit` |

工具记录本次阶段前后的输入 ADF 哈希，任何漂移都会失败。原生报告必须包含正确的 PG2L100H、-6、FBG676 与 `board1080_top`；两个角的十二类表格（setup、hold、recovery、removal、MPW、Skew）均存在且非空，才能认定报告完整。负 slack 与失败端点不会因 PDS 返回码为零而被忽略。

本机 PDS 2025.2 的 `help pnr` 列出 `-input_db_file`，首次真实执行发现该聚合命令未把 DB 路径传给内部 Place action。runner 已改为官方 `UG990004_Tcl_Command_User_Guide.pdf` 第 2.2.4 节的独立 action 流程：`place -input_db_file ... -gplace_seed ...` → `route` → `route_optimize -fix_hold_violation_in_route TRUE`。该流程已成功加载完整 Map ADF 并进入 placement。旧工具脚本中的 `-optimize_multi_corner_timing` / `-fix_hold_violation` 不在 2025.2 帮助列表中。新流程不包含自动位流生成，保留冻结 FDC 的时钟和跨域诊断约束，没有添加旧 camera 路径的 reset 豁免。

PDS 2025.2 的 Map PRT 使用 `pad|site|bank|function|||YES` 表示已预留的位置，尚未填实际端口和方向。Map 审计核对 PCF 的 144 个端口及全部 LOC/VCCIO/IOSTANDARD，再核对 PRT 的 144 个预留位置与 bank 电压。PNR 审计另外要求实际端口、方向和位置全部匹配。Map 预留检查不会写成已完成路由引脚验收。

独立阶段导入 Map ADF 时，PDS 2025.2 未自动继承外部物理/时序约束；首次独立 route 的实际引脚被工具自动分配，审计拒绝该结果，原目录完整保留。后续 route、STA、bitstream 均显式 `add_constraint` 封存 FDC、UART overlay 以及 Map PCF（`-pnr_set pnr_1`），并核对实际 PDS 项目中的约束文件集合。最终引脚报告使用 `_prr_route_optimize.prt`，与最终 `_pnr.adf` 对应；`.rur` 的 IO Port Info 逐项对照 Map PCF 所有端口属性，包括 DRIVE、SLEW、BUS_KEEPER/PULLUP。

route 后的短时序报告核对 11 个时钟名称、类型及周期：board27=37.037037ns、input_pixel=13.315579ns、pixel_clk≈13.468013ns、cfg_clk≈100ns、ref/rst/ddrphy_sysclk 与两个 phy_dq_sysclk 为 8ns、两个 phy_dq_clk 为 1ns。独立完整 STA 再核对这些时钟及十二类检查的正端点覆盖数。时钟缺失、周期改变和空检查表会使阶段审计失败。

工具格式适配可以保留已有成功原生结果，仅重做 CPU 审计：

```powershell
# previous-runner.py 必须是旧执行版本的精确源码快照。
python -B $flow migrate-runner --work $work --previous-runner "$work/provenance/previous-runner.py"
python -B $flow audit-existing --work $work --stage map
```

迁移会验证所有源文件和约束未漂移，保存旧 runner、board-flow、阶段 receipt 与迁移记录；`audit-existing` 只接受原生退出码为零、已有完整成功标记的阶段，不执行 EDA。若原生阶段失败，可用新的编号目录重试并保留原失败记录：

```powershell
python -B $flow run --work $work --stage route --attempt 2 --pds-shell $pds
```

真实 Map 的 144 端口/预留 pad 审计已通过；错误 LOC、电压、IO 标准、缺失预留位置和错误实际方向等 CPU 拒绝检查已通过。完整 routed 数据库与最终 STA 的结果以该 run 的阶段 receipt 为准。

## 正式检查与诊断测试位流

默认 bitstream 阶段要求全部原生时序检查通过，并要求 IO、CDC/复位验收状态通过。当前冻结工程使用 diagnostic FDC，输入/输出 AC delay 与部分 DDR 复位问题尚未签核，因此默认导出会停止。

在已有完整新 STA、器件/144 引脚/声明电压检查通过后，可由主工程师审阅失败项目，再显式生成诊断测试位流：

```powershell
python -B $flow run --work $work --stage bitstream --pds-shell $pds --diagnostic-bit
```

这项操作保留所有失败计数和最差 slack，并把导出文件标记为 **`DIAGNOSTIC_NOT_TIMING_SIGNOFF`**。`physical_timing_accepted` 与 `hardware_release_allowed` 保持 `false`。它供受控上板测试使用，不能在报告中写成正式时序签核或稳定性能通过。

基线记录中仍有 slow setup −0.579ns、DDR recovery/removal 违规、输入/输出 delay 缺失；新优化候选必须用自身的 STA 结果重新判断。流水线改动、缓存扩宽及写回双缓冲不自动消除这些物理问题。

若需要重做 PNR、修改约束、改变 seed 或添加经审查的真实 IO 时序，创建新 run 并重新绑定源码/约束。不得通过删除失败记录、批量 false path 或修改报告通过标志获得导出结论。

最终导出前，工具重新解析当前磁盘中的 STA 和实际引脚/电气报告，核对原生 STA 头中的输入 ADF 路径及其 SHA；导出阶段结束后再次复核全部前置证据。旧 receipt 内的通过标记不能替代当前解析。STA 使用 `-max_path 50 -nworst 4`，保留全部 summary 与失败总数、异常报告和 IO datasheet；逐路径明细按该范围采样。

PDS 启动前检查工作目录所在磁盘至少有 1 GiB 空间。阶段 JSON 先写临时文件再原子替换，磁盘满时保留已有 receipt。2026-11-03 的 C 盘空间不足导致独立 STA 和另外两路 route 失败，原日志保留；后续完整构建使用新的 D 盘 `--output-root`，重新 prepare/map/route，保持源码绝对绑定一致。已有 cache-a route-03 的正确引脚与时钟结果仅作该次构建证据。
