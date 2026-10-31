# DVP 相机入口离线验证（2026-10-29）

本轮将 8bit DVP 的 RGB565 字节流转换成现有采集链的预约、256bit FIFO 和完成信息接口。相机每两个时钟才形成一个像素；不能直接把 pixel_valid 当作旧 HDMI 输入的 DE，否则每个像素之间的空拍会被误判成行结束。新增入口单独处理 HREF、字节配对和帧边界，原 HDMI、DDR 与矫正源码保持不变。

新增文件：

- `distortion/rtl/experimental/dvp_rgb565_capture_cdc.v`
- `distortion/tests/tb_dvp_rgb565_capture_cdc.sv`
- `distortion/tools/run_dvp_capture_cdc_sim.py`

支持 VSYNC/HREF 极性及高低字节顺序参数。只有一帧的首个有效字节能消耗预约；晚到预约等待下一完整帧。短行、长行、缺行、多行、奇数字节、FIFO 溢出和运行中撤销 enable 会将整帧标坏。每个 256bit FIFO 字的最低 16bit 是最早像素，CRC 按 RGB565 低字节、高字节顺序计算。

## 实际验证

最终运行 `distortion/build/dvp-capture-cdc/native-1029-b`，北京时间 23:18:13–23:18:29，Vivado 2017.4 编译、展开、仿真均退出 0。16 个场景通过，覆盖上述故障及恢复、异步时钟与反压、迟到预约、完成信息背压、公共复位清空半像素和队列。两个实例分别验证正常极性/高字节先行与反极性/低字节先行。

首帧 32×4、128 像素、8 个 FIFO 字全部与独立 Python 字节参考一致，zlib CRC32 为 `8fc57a41`。最终回执记录了全部源码及日志哈希，运行后核对没有输入漂移；可共享副本为 `distortion/results/dvp-capture-cdc-20261029.json`。初轮 a 通过后，复位测试增加了真实 half_byte 前置断言，最终结果以 b 为准。

复现（仓库根目录，NEW-RUN 必须是新目录）：

```powershell
New-Item -ItemType Directory distortion/build/dvp-capture-cdc/NEW-RUN
.venv/Scripts/python.exe distortion/tools/run_dvp_capture_cdc_sim.py --workdir distortion/build/dvp-capture-cdc/NEW-RUN
```

本轮没有接入 DMA/DDR/矫正整链，没有 PDS 构建或下载；这些小尺寸合成输入不证明当前相机实际帧率、极性、字节顺序或板级时序。

## 后续集成约束

1. FIFO 字不携带 bank/id。消费端必须先排空 FIFO，再确认 done，之后才发下一次 grant；本模块不自行防止消费端过早确认。
2. done 在下一 VSYNC 才发布；相机停钟或不再产生 VSYNC 时，需要外部健康监测与公共复位策略。不能只复位其中一个时钟域。
3. HREF 下降与 VSYNC 上升同一个采样沿会被保守判坏；当前要求二者间至少有一次独立 HREF 低采样。真实传感器边沿关系未核实。
4. Gray 指针和保持型跨域总线仍需物理约束。参数 WIDTH 要求为正的 16 倍数，FIFO_ADDR_BITS 至少为 2。现有测试没有覆盖最短消隐或最快连续预约的所有相位。

## 当前本机连接

用户确认 OV5640 双目模组和转接板来自淘宝“小眼睛半导体”；配套 FMC 卡按照片布局和原厂手册识别为 MES-FMC-LPC-IO，具体镜头/相机 PCB 版本未核实。

2026-10-29 22:51 的只读 JTAG 扫描识别 PG2L100H / `0x00602899`，DONE=0。原始记录在 `distortion/build/offline-20261024/live-scan-20261029T145129084714Z`。

随后用户接上开发板 UART Type-C 数据线，新增 COM7：Silicon Labs CP210x，VID:PID=10C4:EA60。921600 baud 接收测试成功打开、接收 2 秒并关闭，收到 0 字节，发送 0 字节。COM5/COM6 是原先存在的 FTDI 双通道设备；PDS 下载走 USB Cable II，不按 COM7 下载。当前没有匹配调试位流的有效输出，不能把静默解释为相机故障或出图成功。

旧 `camera_isp_probe_d5-20261029-b` 虽有位流，其报告 slow/fast 各有 16 项 camera_pclk hold 失败，最差 -2.580/-1.723 ns，未用它下载。完整 guarded 原图候选还需本机可移植构建和恢复位流绑定；旧队友采样记录不能当成本板实测。

以上是2026-10-29历史分工，旧“下一轮优先HDMI输入输出”已被取代。DVP模块现已接入640×480摄像头候选，仿真通过，原生构建有DDR hold/recovery失败；实际上板待时序/物理检查完成。用户最新通知板卡断电，上板前先通知。见[摄像头接入交接](CAMERA_VGA_INPUT_20261031.md)，仅HDMI IN支线暂停。