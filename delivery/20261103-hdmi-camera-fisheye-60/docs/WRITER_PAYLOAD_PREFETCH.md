# 写回数据寄存与错误控制分离

`physical-d`（BuildID `11037003`，源码身份 `1cfc559ec1ad25018f691d85febb2a222dc30cbd38a3371a786c8d951b597ed4`）的最差核心路径从 lane FIFO 的 `buffer_tag[1][13]`，经过标签比较、`bad_tag/abort`、发送状态控制，到 `raster/send_data[110]` 的时钟使能。裕量 −3.954 ns，10 级逻辑、数据延迟 11.388 ns，布线占 83.9%；最后一级使能驱动 256 位数据寄存器。局部 `cmd_pixel` 使能存在同类路径，最差 −3.816 ns。

本次修改 `rtl/ddr_adaptive_result_writer.v` 的两处数据捕获条件，正常流水周期保持：

- 首个发送字在 `tx_state==TX_IDLE && full[send_bank]` 时预取。条件仅依赖寄存状态与银行所有权；数据在空闲阶段尚未发布，故障当拍允许更新这份私有副本。
- 局部 `cmd_pixel/cmd_lane` 在 `take` 与本字地址匹配时捕获。真正写入 burst RAM 的 `cmd_pending` 继续使用 `issue=take&&!bad_tag`。错误像素可以进入私有数据寄存器，其命令被阻止，RAM 中的已提交数据保持原值。

发布控制保持原规则：新 AW 同拍受 `failed`、`bad_tag`、`abort` 拦截；AW 已经呈现后，地址与首拍数据保持至接受；后续 W 仅在实际传输时更新下一拍数据。已承诺事务继续完成，失败帧不产生完成发布。突发末拍后的地址递增及银行释放保持原实现。

## 验证

`tools/run_writer_regression.py` 已包含新增的 `tests/tb_writer_fault_collision.sv`。使用 Vivado Simulator 2017.4 运行：

- 48/48 既有回归通过：光栅、8×8、32×8、双条带背压、像素与 CRC、标签/传输错误、复位与多帧模式切换。
- 逐用例比较 `evidence/writer-timing-local-index/report.json`，所有周期、停顿、像素数与 CRC 指标相同。
- 10/10 新增碰撞通过：分别将外部 abort 和错误标签对齐到空闲满 bank 的首拍预取、待接受 AW、AW 与首拍 W 同时接受、中间 W、最后 W。
- 两次空闲故障均完成私有首字预取，同时保持零 AW、零 W；其余八次碰撞完成已有的 16 拍突发，共逐像素核对 2,048 个 RGB565 像素，未出现额外 AW、错误局部命令或完成发布。

证据位于 `evidence/writer-payload-prefetch/`。源码 SHA256 为 `6799f5bd169449ee5eb42593d18d37a6f03ba9cbcf6b04db296fbf4c7c890c8e`。

这些结果覆盖数字功能与握手。更新后的核心物理时序须由包含本源码的新布局布线报告确认；`physical-d` 记录的是修改前路径。整机争用、外部 IO、CDC/复位和实板新帧率验收仍分别记录。
