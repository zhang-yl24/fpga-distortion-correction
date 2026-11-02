# 720p transport 顶层只读审查（2026-11-01）

结论：未发现阻止进入独立离线物理实现的顶层/来源闭包缺陷。本次不是时序、CDC 物理实现、实板或镜头矫正验收；未执行 PDS、下载或硬件访问，未修改任何生产文件。

审查文件及 SHA256：

| 文件（相对 distortion） | SHA256 |
| --- | --- |
| board/camera720_transport_top.v | b71329fe4621f6a820fbc2b4e2513e51bfc06bed4bf87dd4adea42f78d8c0629 |
| board/camera720-identity.vh | 84a8cfc58afc17bed4ee7eae7dcdb90cbe2a7c3edd6d900b52a5b8553435e4a8 |
| board/camera720-output-diagnostic.fdc | 326970a4d6d75128eaa4fd9763d1fbc406c2b78570cf37f1b0ead632ffe1c007 |
| tools/prepare_camera720_output.py | 57779b542f80ac2b245af89dec6921ef60e6839d314a33d43f48c040a99cbbf0 |
| board/camera720-output-sources.json | a4f6257c8614b43ebe8d09beef764a8d0f06c31d2d474755b8e5865a55009be5 |
| rtl/experimental/ov5640_current720_frontend.v | 6e412ed815c8df4ac04b89a71c595416fa76f4207926179b005c162f4ebfc39a |
| rtl/experimental/dvp_mode_admission_monitor.v | 2895bad17ecc74c0cceefce4a53de525a2516462e1bc082481d2d34de2ec8b55 |

## 准入与复位

- 顶层 VS/HREF 物理输入各取反后送监测器，采集系统同时使用 `VSYNC_ACTIVE_HIGH=0`、`HREF_ACTIVE_HIGH=0`、`HIGH_BYTE_FIRST=0`。监测器按 2560 字节/行、720 行/帧计数，直接使用 camera PCLK。
- `camera_ready` 连接 frontend 的 `raw_authorize`，并非 `configured`。真实 frontend 要求至少两完整好帧及各项 freshness；启动宽限为 27,000,000 个 27 MHz 周期。顶层还保留 8 秒连续 readiness warmup，以及 DDR/TX/video ready 条件。
- `pipeline_release` 置位后仅共同复位会清零。初始化/监测器错误、准入丢失以及其它运行故障会粘滞锁存 `board_failed`，经双触发器同步到 core，停止新采集/显示准入；`pipeline_reset_n=global_reset_n && pipeline_release` 不随运行故障下降，不会由监测器局部复位清除 DDR/FIFO/bank epoch。
- 顶层 `board_fault` 是与 `board_failed` 同拍锁存且保持的总线，等待双级 `board_failed_core` 后由 core 使用。该已有 held-bus 模式仍需此次原生路径检查；没有把任意逐拍变化总线直接当同步状态使用。
- 顶层仅使用 sensor 故障总类 A8/A9，`camera_fault` 和详细 frontend 诊断输出未导出，预计会被综合优化。不能声称该位流已经提供 UART 诊断或精确监测计数读回。

## 恒等映射与存储尺寸

- 配置中心为 (639.5, 359.5)，源/目标中心相同；焦距 1024 和逆焦距 1/1024 均在定点格式精确可表示，五个畸变项为零。
- 使用现有独立 CPU 整数 Brown oracle `generate_1080_core_vectors.project_integer` 检查全部 921,600 个整数输出像素：坐标不匹配 0、无效坐标 0，最大 r² Q22 为 2,152,802，低于 guard 8,388,608。左上结果 (0,0)，右下 Q15.8 结果 (327424,184064)，即 (1279,719)。本检查未读取 RTL 输出生成期望值。
- 边缘像素整数采样的 fx/fy 为零；sampler 对单个越界邻点置黑，未将整块部分越界 footprint 强制黑屏，因此最后一行/列的零权重邻点不会破坏恒等映射。仍应由实际全尺寸 RTL 回归确认像素和 CRC。
- 一帧 1,843,200 bytes = 57,600 个 256-bit beats = 460,800 个 4-byte UI 单位；`BANK_STRIDE=1,048,576` UI 单位即 4 MiB，可容纳一帧。四 bank 地址布局和 DDR 实例/tie-offs 保持原样。
- 1280×720 原生图像居中于 1920×1080 active area；实际 raster 位置 WX=512、WY=221，对应 active area 内偏移 (320,180)。没有把 VGA 拉伸称作 720p。

## 闭包与约束

- `validate_sources()` 实际通过；111 个 manifest source，30 个显式 Verilog + 1 个 IDF，74 个 IDF 展开源不重复 add，5 个 header 不作为独立 design；旧 sensor init/table、top、mapping header、FDC 均从候选角色中移除并替换。
- 新 top 与 `expected_top()` 精确一致，修改范围为 top 名称、尺寸、frontend 替换和恒等映射 include；DDR 实例和全部 pad 端口声明保持原始文本。新 FDC 与声明的旧 FDC 原始字节加两行注释精确一致。
- 新 manifest 明确 `InheritedPhysicalTimingPass=false`、`OpticalCorrectionAccepted=false`、`HardwareReleaseAllowed=false`，PinAudit 明确外部 IO 尚未验收。没有继承旧 VGA 布局布线通过结论。
- camera PCLK 20.833 ns、输入 0..5 ns 仍为工程预算；与 27 MHz 域的双向跨域路径上限 8 ns 已存在，但这只证明存在约束文本，不证明对象匹配或路由通过。

## 本次物理实现后仍必须检查

- 监测器逻辑新增 32-bit edge Gray、16-bit VS Gray、16-bit HREF Gray、105-bit logical held snapshot、req/ack/healthy/fault 同步器及 p_reset/r_reset。综合可裁剪未用诊断字段；以实际存活端点为准核验每条路径和级间时序，而非复用旧 VGA 34-bit Gray 枚举或强制虚构 105 个存活 held bits。
- 必须验证 Gray 源寄存器到第一级同步器的覆盖/最大延时及源周期界限；held snapshot 在 req/ack/settle 握手下的稳定时间；新增 monitor_reset_n 的恢复/移除与本地同步释放。旧复位 endpoint 名称/例外不能直接粘贴。
- 独立检查 128 pads、数据输入 delay primitives、VS/HREF 新增首级采样端点，以及完整 slow/fast 时序表。48 MHz 预算不构成真实 PCLK/XVCLK 或外部 AC 测量。
- 实板 transport、该模式的光学标定/校正及 720p 帧率仍未验收。现有 VGA 标定没有被新 top 使用。

本报告只支持继续离线实现；不批准位流或上板操作。
