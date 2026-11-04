# Lane DDR 返回寄存

G 在每个 lane 的 cache 输入前增加一拍 DDR 返回整束寄存：data、ID、last 每拍更新，valid 在共同 reset 时清零。AR 路径保持原握手。这个边界缩短两层 read arbiter 状态到 cache RAM 写使能的路径，代价为每次 cache miss 增加一拍返回延迟。

lane 的宽 payload 不使用原始 rvalid 作为 256 位 CE，data、ID、last 与 valid 始终同拍对齐。协议所有权检查由外部读返回保护和 arbiter 保持；lane 的这一拍寄存不代替整机协议保护。最终整机还包含 `ddr_read_return_register.v` 的独立 raw-owner guard，应结合父级接口和系统回归检查。

`evidence/lane-return-register/report.json` 绑定 lane SHA `45f7691934f7c683107d7a213bbcc7173167ecbd29319f63adea233d1277b26b`。真实 lane 加 core/writer 替身测试覆盖 130 次 payload 逐周期对齐、30 次有效返回、82 个空泡、6 次 AR 与首 R 同拍、pending-valid 的共同 reset 取消，以及错 RID、早 last、漏 last 三类故障传播。`evidence/lane-launch-return/` 同时复验本地 launch 与 FIFO2，6 帧完整通过。

这些单元证据限定到记录的 lane 版本与替身边界。全帧像素/CRC、实际 DDR 仲裁争用和新构建时序应使用对应构建的整引擎、system 和 native 证据。未操作板卡。
