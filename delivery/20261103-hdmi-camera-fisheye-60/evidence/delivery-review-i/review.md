# I 交付证据一致性复核

审查通过，共 44 项检查；核对状态文件引用的 12 份证据 SHA-256。此结论仅确认源码候选的说明与证据一致。整体物理时序仍失败，板测与新位流验收继续待完成。

源码身份：`d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5`，116 个编译输入；已核对冻结原生目录全部文件哈希、两次全帧仿真及系统仿真的源码绑定。

| 检查 | 时钟关系 | 最差裕量 ns | 失败端点 |
| --- | --- | ---: | ---: |
| slow_setup | ddrphy_sysclk → ddrphy_sysclk | -2.886 | 3601 |
| slow_setup | input_pixel → input_pixel | -2.414 | 433 |
| slow_setup | cfg_clk → board27 | -0.331 | 1 |
| slow_setup | ddrphy_sysclk → phy_dq_sysclk_0 | -0.012 | 3 |
| slow_recovery | board27 → cfg_clk | -0.403 | 7 |

五组同域或相关域失败与全部十二类原生汇总逐项一致。独立时钟域路径继续按 CDC 范围报告，未与已通过的 34 条 Gray 同步结构和两角 6 ns 边界检查混为整机验收。外部 IO、held-bundle CDC、复位释放和 MTBF 保持待验收。

README 的 73.834 / 60.192 FPS 对应指定 DDR 压力模型；2,073,600 像素、CRC、系统 32 个唯一帧和 151,552 显示像素均与 I 证据一致。writer beat 的 232 个实际寄存器副本及最大扇出 32 属于局部证据，全局时序状态仍为 FAIL。

候选目录未发现编程文件，状态为 NOT_GENERATED、board_ready=false、hardware_tested=false。README 已区分保留的原 C 版约 4.28 FPS 位流。压缩包内容与归档 SHA 由后续打包步骤核验。

审查 README SHA-256：`398058a7292d645a2f3392daffbc588e4726d16365b9148b8952ae739d648dae`。
审查 VALIDATION_STATUS SHA-256：`eb0d6636d710577b3ee05a4646fdc7cfc7c57b4c3faf2f269234c52fc1efada0`。
