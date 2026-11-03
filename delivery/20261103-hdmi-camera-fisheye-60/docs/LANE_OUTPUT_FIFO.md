# Lane 输出握手流水

physical-b 核心最差路径从 lane 1 的 writer `accepted_pixels[12]`，经 writer `in_ready`、lane `result_ready` 和采样流水使能，到 `query_cached_valid`，裕量为 −3.264 ns。原单项 elastic 缓冲中的 `!buffer_valid || writer_input_ready` 形成了这条组合反馈路径。

lane 输出现使用两项完整 RGB/tag FIFO。采样器 ready 只依赖寄存的 `buffer_count<2` 与寄存的故障状态，满 FIFO 当拍弹出时仍暂停入队。占用一项时允许同时入队和弹出，连续吞吐保持每拍一个像素。遮罩在入队时将 RGB 置零，标签与像素一起保存；新帧准入要求 FIFO 已排空，共同复位和故障会清除占用状态。

lane 源码 SHA256：`dc664bfc2c9a4511eb3ba794cee0d3e758b1d972929bd21a2b35517be8c5aa48`。

已完成两层验证：

- `evidence/lane-fifo2/`：真实 lane RTL 配合可控 core/writer 测试替身。4 个完整帧、2,053 个出队像素/标签检查、1,364 拍满 FIFO、297 次满状态弹出、1,752 次同时进出、126 个遮罩像素；覆盖 FIFO 非空时复位、故障隔离及复位恢复。
- `evidence/system-lane-fifo2-8/`：8×8、rowpad 配置的真实 64×64 系统，两次复位周期合计 34 个接收源帧、33 个发布帧、32 个唯一显示帧及 5 次重复显示。源、结果和显示均逐像素检查，CRC 通过，欠流和不匹配为零；包含共享 DDR 争用、原图/校正切换及处理中共同复位。

64×64 系统中的 rowpad 按参数规则回退到线性索引，原生 1920 宽 row16 索引另由缓存定向测试和全尺寸引擎测试覆盖。新的 FIFO 需要随最终闭包重新检查全尺寸吞吐和物理时序，以上数字功能验证不代表时序已经收敛。

复现：

```powershell
python tools/run_lane_fifo_checks.py --work D:/f60-test-lane
python tools/run_system_contention.py --work D:/f60-test-system --tile-width 8 --cache-profile rowpad
```

工作目录必须尚不存在；可用 `--vivado-bin` 指定 Vivado XSim 安装目录。
