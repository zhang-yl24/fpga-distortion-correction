# G FIFO 原生结构与连接核验

冻结身份：`7a246494adf458b607d430b9ebc60c13420f7f859352edb82ad6211e0a20eb8b`；Build ID `11037003`。源 FIFO SHA-256：`143400186f0549f30007e64cd7dbcc6b82395099f7c2dd85e92725cb06943a16`。本次只读检查未修改 RTL 或时序约束。

综合与原生映射检查通过。两个 FIFO 共 34 条 Gray 指针同步链，布线后为 68 个独立 `V_FFSYN`（route object 为 `gopQ`），FIFO 内 SRL 为 0。每位均核验真实源寄存器 Q → 第一拍 D → 第二拍 D，目标时钟和常开 CE 正确。最高位依据实际 binary 寄存器别名核验。

复位逻辑保留两条完整二级链，共 4 个 `V_FFASYN`：顶层 `core_reset[0:1]` 与 `system/display_fifo/rd_reset_sync[0:1]`。两个 FIFO 的同域复位允许综合共享；逐级核验了恒 1 首级 D、两级直连、共同异步清零和目标时钟。每条 Gray 链的 SR 经实际 `V_INV`/`V_BUF` 回溯到对应 owner 的第二拍 Q。

阶段证据：综合 VM 全部 68 Gray + 4 reset 保留原生属性；device-map `.dmr` 逐项记录全部 72 个 `PAP_ASYNC_REG=TRUE`；最终 `.pnr.adf` 只读导出的功能网表直接证明最终物理两级结构和逐边连接。PDS `gen_netlist` 对 `_map.adf` 返回 `Flow-0013`，仅接受 Place & Route 数据库，因此 devmap 独立连线导出未取得；拒绝日志保留。

PDS 综合 CDC 记录为 4 条 `CDC-3`（binary MSB）和 4 条 `CDC-6`（Gray 向量），均为 `with ASYNC_REG property`、Category `Safe`。原始 CDC 表已归档。这是结构识别结果。

现有 bounded slow setup 报告包含 pixel → core 的 17 条 FIFO Gray 源到第一拍路径，Data delay 为 5.978–6.171 ns；逆方向 17 位未在该有界报告内。尚需分别对 core → pixel（源周期 8 ns）与 pixel → core（约束源周期 6.6667 ns）施加、核验精确 max-delay 和 bus-skew，以及所有位的实际结果；当前报告未签署该项验收。两级之间保留目标域同步时序。未增加 broad clock-group 或 false-path。

Gray 一位变化条件：每个本地时钟最多一次合法 FIFO 接受，binary 加 1 后寄存 Gray，因此正常运行每沿改变 0 或 1 位。公共复位可清零多个位，复位跳变不套用该条件；复位期间 ready 禁止接受，并由本地二级链释放。

与功能证据绑定：`../system-final-g-rowpad640-fanout16/physical-g-source-binding.json` 证明系统回归和 G 原生工程原始 overlay SHA 全一致；真实系统两 epoch 通过。64×64 系统覆盖 small-width fallback；native 1920×1080 rowpad 路径由 cache 单元与父代理完整帧仿真覆盖。

复核入口：`fifo-g-audit.json`（syn/devmap/route objects）；`fifo-g-mapped-audit.json`（34 条最终连接、复位回溯、17 条实际时序）；`gray-constraint-endpoints.json`（稳定综合名与实际映射 pin）；`fifo-g-mapped-primitives.v`（真实网表节选）。75 MB 完整 sim 网表保留于 `D:/f60-work/cdc/g-netlist/prj_tasks/pnr_1/generate_netlist/hdmi_camera_fisheye_top_sim.v`，其 SHA 与输入 PNR ADF SHA 已写入审计 JSON。
