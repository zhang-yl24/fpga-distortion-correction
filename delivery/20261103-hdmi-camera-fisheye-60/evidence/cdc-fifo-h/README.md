# H FIFO 原生结构与连接核验

冻结身份：`fe756ccb51cbbf1ea30a337eec0c22d5419fd4cdb5cd34dad2097bcde880e44d`，Build ID `11037003`。源 FIFO SHA-256：`143400186f0549f30007e64cd7dbcc6b82395099f7c2dd85e92725cb06943a16`。本次审计只读。

两 FIFO 的 34 条 Gray 指针同步链检查通过：68 个独立 `gopQ`，最终 PNR 功能网表对应 68 个 `V_FFSYN`；每位实际源 Q → 第一拍 D → 第二拍 D 直连、目标时钟和常开 CE 均正确，FIFO 内 SRL 为 0。H 的精确约束保留了四个源 Gray MSB 的命名；审计按实际源 net 核对，低位严格匹配 Gray，最高位允许等价 binary 别名。本次 H 最高位实际均为 Gray。

复位由两条完整二级链共 4 个独立 `V_FFASYN` 提供：`core_reset[0:1]` 和 `system/display_fifo/rd_reset_sync[0:1]`。每条链的第二拍直接取第一拍 Q；时钟和异步复位一致。顶层 core_reset 首级 D 的命名常量 `_VCC788` 已追溯至 `VCC_788/FYC/LUT6CARRY` 的全 1 INIT，其输出恒为 1；其余首级 D 为字面常 1。所有 Gray FF 的 SR 经实际 V_INV/V_BUF 回溯到所属共享复位链的第二拍。

综合 VM 对每条链验证连接及 `PAP_ASYNC_REG=TRUE` / `PAP_SRL_STYLE=registers`。Device-map DMR 对 68 Gray + 4 reset 共 72 个寄存器逐项保留 PAP_ASYNC_REG。最终 route objects 与从真实 PNR ADF 只读导出的完整网表证明物理结构。G 的工具能力探针确认 `gen_netlist` 拒绝单独 `_map.adf`；device-map 阶段使用属性记录，最终物理连线直接从 H PNR 网表核验。

H 综合 CDC 表为 4 条全宽 `CDC-6`、`Multi-bit synchronized with ASYNC_REG property`、Category `Safe`。原始表已归档。精确 Gray 时序由另一份独立报告验收：`../cdc-user-audit/physical-h-gray-constraints.json` 为 PASS；slow/fast 各核验 34 条 source→first 路径和 4 组 skew，slow 最大 Data delay 1.011 ns、最小 slack 4.853 ns、最大实际 skew 1.170 ns，fast 对应 0.623/5.303/0.853 ns。该结果范围为 FIFO Gray 的精确约束；其他 CDC、内部时序、外部 IO 与板测分别验收。

与系统功能绑定：`../system-final-h-rowpad640-fanout16/physical-h-source-binding.json` 核对全部 116 个闭包文件及原始 overlay。两 epoch 真实系统通过；原生完整 1080p 行为由单独 engine 回归覆盖。

入口：`fifo-h-audit.json`（syn/devmap/route objects），`fifo-h-mapped-audit.json`（每位最终连接、共享 reset 回溯、数据库与网表 SHA），`gray-constraint-endpoints.json`（34 位真实端点），`fifo-h-mapped-primitives.v`（真实网表节选）。完整 PNR 网表保留于 `D:/f60-work/cdc/h-netlist/prj_tasks/pnr_1/generate_netlist/hdmi_camera_fisheye_top_sim.v`。
