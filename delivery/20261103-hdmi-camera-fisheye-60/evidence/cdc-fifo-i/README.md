# I FIFO 原生结构与连接核验

冻结身份 `d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5`，Build ID `11037003`。

两个 FIFO 的 34 条 Gray 同步链逐边通过：全部实际源 Q → 第一拍 D → 第二拍 D 直连，68 个独立 V_FFSYN/gopQ，同目标时钟、常开 CE；FIFO 内 SRL 为 0。4 个共享复位 owner V_FFASYN 构成两条完整二级链，每条 Gray SR 经实际 INV/BUF 回溯到所属复位第二拍。首级常 1、复位和时钟均核验。

综合 VM 对连接、PAP_ASYNC_REG/PAP_SRL_STYLE 检查通过；device-map DMR 全部 68 Gray + 4 reset 原生属性保留；最终 PNR ADF 导出的功能网表直接证明物理两级结构。完整实际 34 位 source/first/second pin 表在 gray-constraint-endpoints.json。

独立精确 Gray 验收在 ../cdc-user-audit/physical-i-gray-constraints.json，状态 PASS，slow/fast 各 34 条 delay 和 4 组 skew；slow 最大 delay 1.306 ns、最小 slack 4.558 ns，fast 0.799/5.127 ns。该通过范围限于 FIFO Gray 结构和精确约束。I 整体物理时序仍未收敛：core 最差 −2.886 ns，3601 个失败端点，当前交付为源码候选。

真实系统功能及全部 116 个文件闭包绑定见 ../system-final-i-rowpad640-fanout16。源 FIFO SHA-256 为 143400186f0549f30007e64cd7dbcc6b82395099f7c2dd85e92725cb06943a16。PNR ADF/完整导出网表 SHA 已写入 fifo-i-mapped-audit.json；真实 primitive 节选一并归档。完整导出网表位于 D:/f60-work/cdc/i-netlist/prj_tasks/pnr_1/generate_netlist/hdmi_camera_fisheye_top_sim.v。
