# DDR IP 与约束审计

静态审计结果为 `PASS_STATIC_PENDING_NATIVE`。证据：`evidence/ddr-constraint-audit.json`；复跑工具：`tools/audit_ddr_constraints.py`。本审计读取当前 C 源码闭包与仓库内厂商参考，避免依赖旧 stable30 的编译结论。

physical-b 的原生审计已通过，证据为 `evidence/video-control/physical-b-diagnostic/ddr-audit.json`，绑定源身份 `19771fce0efe486aa71a8f874376446a6f9966bdce44e6a03824172403857fa6`。约束正确导入，DDR IP 内的时钟叶端点归属及用户时钟关系检查通过；该候选仍有 setup 失败路径。工具对零负载转发时钟计数为 0，clock 报告只封存端点数量、SHA-256 和异常端点。

## IP 身份

- Pango Logos2 HMIC_S 1.10，IP ID 042003。
- 器件 PG2L100H，封装 FBG676，速度等级 -6。
- IP Compiler 2022.2-SP6.4 build 146967；IDF `CLKIN_FREQ=125.000`。
- 当前 `ddr3_test.idf`、顶层、PHY 顶层、复位同步器、PHY 复位控制、slice top 六个文件与仓库厂商参考 SHA-256 全部相同；371 个 IDF 参数全部相同。
- C 基线通过 PDS 2023.2-SP3 构建。当前机器具有 PDS 2025.2；新版必须重新综合、布局布线和 STA。

参考路径：`vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/ddr3_test/ipcore/ddr3_test/`。厂商 FDC 在 `pnr/ddr_test.fdc`，RCF 在 `pnr/ddr3_test.rcf`。工具通过 `git show HEAD:<path>` 获取参考，并将实例前缀 `I_ips_ddr_top` 映射为 `u_ddr3_test_h`，参考时钟端口 `ref_clk_p` 映射为 `clk_p`。

## C 版已有内容及补充范围

C 版主 FDC 已包含六个 DDR 生成时钟、core 到两组 divided PHY 的两条 multicycle=2、双向四条 0.4 ns uncertainty，以及相关位置/电气约束。`build-inputs/build-c.tcl` 第 34/35 行显式导入主 FDC 和 `board1080-ddr-ioclk-priority.rcf`。这证明其构建脚本声明了导入；本次新版仍需检查实际 PDS 输入和 route 日志。

C 主 FDC 缺少厂商参考中的 `rst_clk`、`phy_dq_clk_0`、`phy_dq_clk_1` 三条 asynchronous clock-group 关系。本包用独立文件 `ddr-ip-clock-relations.fdc` 补充同样的三条命令。厂商示例的 `free_clk`、`ref_clk` 两组未迁移。从 H 起，用户 core/pixel 域增加 `constraints/gray-pointer-cdc.fdc` 的四组精确 Gray 指针边界：34 位源指针寄存器（包含 binary MSB 别名）到第一级同步器，分别施加 6 ns `set_max_delay -datapath_only` 和 6 ns `set_max_skew`。这八项命令须逐位核对实际路径，来源与目标之外的路径不在作用范围内；未新增用户全域 clock-group 或 false-path。详见 `CDC_USER_PATH_AUDIT.md`。

单独 `-group` 会切断该组与其他所有时钟的关系。最终 STA 必须证明上述三域及相关 divided PHY 的全部叶时钟端点都位于 `u_ddr3_test_h/` 内，并确认 `ddrphy_sysclk` 到 `phy_dq_sysclk_0/1` 的关系继续参与分析。主 FDC 的两条 multicycle 和四条 uncertainty 保持完整。

本包 RCF 保留两个精确优先网络：

```text
u_ddr3_test_h/u_ddrphy_top/ddrphy_ioclk_gate [0]
u_ddr3_test_h/u_ddrphy_top/ddrphy_ioclk_gate [1]
```

## 最终构建检查

审计工具支持：

```powershell
python -B tools/audit_ddr_constraints.py --output audit-final.json `
  --native-project path/to/map/project.pds `
  --native-project path/to/route/project.pds `
  --native-project path/to/sta/project.pds `
  --route-log path/to/run_route.log `
  --report-db path/to/report_timing/report_db --require-native
```

脚本核对 FDC/RCF 的内容哈希及格式、route 日志中两个优先命令的成功执行、最终 clock network 叶端点归属，以及用户域和 core/divided-PHY 关系未被切断。使用 `--require-native` 时缺少阶段证据会失败。尚需独立检查 setup/hold slack、未约束端点、外部 HDMI AC、物理 CDC/复位和板上稳定运行。加密厂商复位同步器的内部级数尚未独立验证。

## DDR CA 扇出实验

physical-c 通过独立 FDC 给精确网络 `u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/all_group_ca_dly` 设置 `syn_maxfan=16`。已有时序与布线约束、全部 DDR 厂商源码与 physical-b 完全一致。`tools/audit_ddr_ca_fanout.py` 核查 PDS 注册、综合约束检查记录和实际综合网表：两条网络带有 `PAP_MAX_FANOUT=16`，两个驱动均为 `LUT4 INIT=FFFE`，四个输入仍为 `debug_data[66/135/204/273]`。全部 16 种输入组合输出一致，新增寄存延迟为 0。

证据 `evidence/video-control/physical-c-diagnostic/ddr-ca-synthesis-audit.json` 支持局部复制逻辑的布尔等价及属性生效。实际布线扇出与时序裕量需要最终 PnR 报告，整芯片形式等价尚未执行。
