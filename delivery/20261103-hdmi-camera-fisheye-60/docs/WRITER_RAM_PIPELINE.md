# 条带 RAM 输出流水

`physical-e`（源码身份 `49ada7d5a4a1f0ce67bd83a6aef88dcf00f84eda3f92d3fda9aabcc4de74bc3d`）的核心最差路径从 lane 0 的 `writer/stripes_12` RAM 读时钟，经过 RGB 数据分发，到 `raster/crc[27]`。裕量 −2.728 ns，数据延迟 10.217 ns，布线占 81.0%。原 `pixel_q` 被实现为 RAM 的同步读输出，因此 RAM 时钟到输出和 CRC 输入逻辑处于同一周期。

写回前端现在使用两个独立的弹性级：

1. `raw_q/raw_tag/raw_valid` 保存同步 RAM 读结果及标签。`advance_raw = !raw_valid || advance_pixel`，有空位或后级接收时才发起下一次读取。
2. `pixel_q/pixel_tag/pixel_valid` 在 `advance_pixel = !pixel_valid || r_in_ready` 时接收上一拍已捕获的 raw 数据。后级停顿时，该级保持数据和标签。

两个级的使能独立，RAM 读取与 CRC 输入之间增加完整的寄存边界。连续传输仍为每周期一个像素；正常无背压的测试帧只增加一个启动周期。

银行所有权保持原规则：最后一个地址的读结果在时钟边沿进入 raw 寄存器后，才清除该银行的满标志。下一周期可重用这块 RAM，最后一个像素已由 raw/pixel 级持有。背压时禁止覆写有效 raw 数据；共同复位及帧失败清除两个有效位，已承诺的 DDR 突发继续按原协议完成。

## 验证

`tools/run_writer_regression.py` 使用 Vivado Simulator 2017.4 完成 **50/50** 组回归和 **10/10** 组故障碰撞：

- 保留原 48 组光栅、8×8、32×8、像素/CRC、AW/W 背压、标签/传输故障、多帧和复位验证。
- 增加 8×8、32×8 各一组 raw 与 pixel 同时占满时复位，随后完整帧恢复成功。
- 每周期检查 raw 数据/标签在背压下稳定、阻塞时不发新 RAM 读取；正常帧覆盖最后一次读取后下一拍立即复用同一银行。
- 3,072 像素的正常条带帧为 3,892 周期，前版为 3,891；CRC 均为 `6a95746d`。严重 AW 背压样例仍为 7,620 周期，输入停顿由 3,729 降为 3,728。随机背压相位随新增周期变化，最终像素/CRC 全部一致。
- 10 组故障碰撞继续验证空闲预取、新 AW 拦截、已承诺 AW/W 保持与失败帧不发布。

证据为 `evidence/writer-ram-pipeline/`。writer SHA256：`8fbcdf207c6318a858b213bc3d4b1896143c649b8b7b924d0d86165ca619a224`。

本轮数字验证证明顺序、数据和握手行为。寄存边界的物理实现与新最差路径由下一轮 PDS 综合、布局布线和 STA 确认；旧 physical-e 证据保留作为修改依据。
