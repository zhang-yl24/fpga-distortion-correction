# Writer 私有 payload 预取时序修复

RTL SHA-256：`c82d52ad9adc0c53901bac3e07b6fbcfa99a1e28afb1c2985808dd61ca78ec11`。

G 最差 core setup 路径为 lane1 `raster.active` → `r_in_ready` → `take` → `local_command[20].cmd_pixel` CE，slack −1.929 ns，Data delay 9.323 ns，其中 route 8.090 ns。

每个局部 command 的 pixel/lane 现在仅依据寄存的 `{fill_bank,slot[7:4]}` 预取。`cmd_pending` 的 reset、failed、issue 条件完全保留。合法 issue 边沿捕获匹配 payload，下一边沿 burst 消耗旧寄存值，当前边沿的新预取由非阻塞赋值在消费后更新。无效输入、停顿、故障和复位可以改变私有值，均不能自行发布 burst 写入。既有 reset 边沿允许前一 pending 命令退休的行为保持一致。

数字验证全部通过：

- `writer-h-payload-prefetch/report.json`：原 50 项 raster/tile8/tile32 回归及 10 个 fault-collision 场景，检查像素、CRC、AW/W 保留、背压、复位恢复和模式切换。
- `writer-h-publication/report.json`：新增 8 场景，2092 个边沿逐一比对全部 32 个 burst word，1861 个合法命令退休；230 次未发布预取、34 个背压边沿、65 个 fault 边沿、50 个 reset 边沿；已有 pending 与 reset/bad_tag/abort 分别碰撞 2/2/3 次，7 次 bank wrap。
- `tools/run_writer_publication.py` 可独立复现新增检查；输入接受次数独立生成预期 word/lane/pixel，所有实际 burst 变化必须对应先前接受的合法命令。

本组证据覆盖单元行为。G 是修改前的原生时序快照；该修改的原生时序收益与整机组合结果由后续冻结快照验收。
