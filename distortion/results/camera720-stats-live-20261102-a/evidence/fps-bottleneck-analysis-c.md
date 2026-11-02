# 720p 15 FPS 瓶颈分析

## 当前证据

统计版在实际板上运行后，30 秒采集得到 30 个完整 UART 包、29 个有效窗口；120 秒采集得到 120 个完整包、119 个有效窗口。两次采集中输入接受、处理完成和唯一输出计数都为 **15.0 FPS**，身份不匹配和拒包均为 0。

这说明在当前 cadence 下没有观察到输入接受到处理、处理到唯一输出之间的计数缺口。它还不能单独证明传感器真实帧率，因为 `source_accepted` 是采集端接受事件；UART 没有独立 PCLK、HDMI 刷新率、欠流或故障状态。

## 最可能的原因

当前 OV5640 720p RGB565 配置的静态模型是 42 MHz PCLK、约 14.999 FPS，与实测 15.0 FPS 数值一致，因此首先应怀疑传感器模式/输入节拍。这个一致性仍是旁证，实际 PCLK 和 `good_frames` 尚未测量。

下游处理并没有被现有证据证明是瓶颈。已有两帧模型显示 commit→release 约 14.07/14.09 ms；派生的 SCATTER 结构成本约 6.43 ms/两帧，若把每次 fill 从 32 周期压到 16 周期，理论同 fill 数节省约 1.607 ms/帧，但没有实际硬件收益证明。

## 下一步最小候选

先保留当前矫正、双银行、CRC 和 DDR 契约，做一个只读仪表候选：增加 PCLK 边沿、传感器 good/bad、DMA 完成、source accepted、processed、unique presented、pending/display grant 等等待分类，以及 process-cycle 和 cache miss/fill/scatter 计数。

如果 PCLK/good-frame 本身约为 15 FPS，就建立隔离的 720p30 OV5640 模式候选（资料模型使用约 84 MHz PCLK），明确读回、实际测频、2560 字节×720 行新鲜度和新的输入时序约束；不覆盖当前 15 FPS 位流。如果输入更快而处理或显示计数落后，再分别做调度或 cache/scatter 实验。

完整数据和输入哈希见同目录的 `fps-bottleneck-analysis-c.json`。
