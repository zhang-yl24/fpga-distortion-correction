# HDMI 摄像头 1080p 30 FPS 技术说明

本项目已在本地下载队友交付位流，通过实际 HDMI 摄像头验证 **1920×1080 鱼眼矫正达到 30 FPS**。本页依据用户本轮现场确认，以及 2026-11-04 留存的源码、位流和时序资料整理。

## 版本与下载

现场验证对应 `delivery/20261104-op-camera-input-diagnostics`，提交 `dbf928e91082e7c81b5a188b8b464726040da0a7`。位流名为 `camera-op-input-firstloss-timing-unclosed4-setup-minus32ps-diagnostic.sbit`，大小 3,791,112 字节。

- [a266 位流](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261104-op-camera-input-unclosed4-diagnostic/camera-op-input-firstloss-timing-unclosed4-setup-minus32ps-diagnostic.sbit) · [位流身份](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261104-op-camera-input-unclosed4-diagnostic/DIAGNOSTIC_IDENTITY.json)
- SHA256：`a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547`
- 器件：Pango Logos2 PG2L100H-6 FBG676；工具：PDS 2025.2 ADS。
- 源码由 [基础核心源码清单](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261103-hdmi1080-demo-source/stable30-OP/SOURCE_BINDING.json) 与 [诊断源码清单](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261104-op-camera-input-diagnostics/SOURCE_BINDING.json) 共同描述，诊断增量源码提交为 `f8f58a161111ecbac3400d0629a5064d43c405d8`。

帧率依据本轮摄像头现场验证。该现场版本的处理耗时、端到端延迟及持续测试时长需单独记录。输入与输出采用名义 148.5 MHz 的 1080p60 视频时序；60 Hz 显示扫描与每秒新生成的校正结果分别统计。

## 数据通路与提帧机制

```text
HDMI 摄像头 → MS7200 → 输入资格检查 / DMA → DDR 源帧
    → 8×8 分块遍历 → 鱼眼逆映射 → 查询队列 / 前瞻预取
    → 四邻域采样与双线性插值 → 分块行突发写回 → DDR 结果帧
    → 完整帧发布 / 显示交接 → HDMI 输出
```

**按块处理与定点映射。** [帧处理引擎](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261103-hdmi1080-demo-source/stable30-OP/native/source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/pipeline_gamma_frame_engine_1080_geometry_bypass.v)按 8×8 块产生目标坐标和全局像素标签，[鱼眼逆映射](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261103-hdmi1080-demo-source/stable30-OP/native/source/profile/rtl/experimental/hdmi_camera_fisheye_mapper.v)依据镜头参数和径向表计算源坐标，[采样与双线性插值连接](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261103-hdmi1080-demo-source/stable30-OP/native/source/rtl/experimental/ddr_remap_sample_scatter4.v)读取四个邻域像素并做双线性插值。当前鱼眼配置为 0°、Gamma OFF；源码保留其他模式的接口。

**用前瞻预取覆盖 DDR 等待。** [运行时预取缓存](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261103-hdmi1080-demo-source/stable30-OP/native/source/rtl/experimental/d256_runtime_prefetch_cache.sv)采用 512 项查询队列、256 项前瞻和 INDEX6；[四邻域预取存储](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261103-hdmi1080-demo-source/stable30-OP/native/source/rtl/experimental/quad_parity_prefetch_store.sv)按奇偶坐标组织四邻域数据，以 SCATTER8 方式填充。缓存分别维护活动代与待填充代，按查询引用计数保护尚在使用的缓存行，避免预取覆盖待消费数据。查询顺序与像素标签贯穿背压和返回路径。

**收集与写回重叠。** [分块行突发写回](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261103-hdmi1080-demo-source/stable30-OP/native/source/rtl/experimental/ddr_tile8_rowburst_writer.sv)使用两组 64×8 缓冲区，一组收集像素，另一组按行突发写 DDR。RGB565 数据通过 256 位接口传输，每拍 16 像素，64 像素行对应 4 拍、`AWLEN=3`。分行 CRC 合并为全帧光栅顺序 CRC，完成最后写回与排空后才发布结果。

**完整帧所有权。** [帧缓冲管理](https://github.com/zhang-yl24/fpga-distortion-correction/blob/dbf928e91082e7c81b5a188b8b464726040da0a7/delivery/20261103-hdmi1080-demo-source/stable30-OP/native/source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/lens1080_bank_core_geometry_bypass.v)管理两个源帧区和两个结果区，每区步长 4 MiB。接收源帧时锁存参数与模式；处理期间锁定源帧，完成后进入 pending，显示接管后切换结果区，显示释放前保护正在扫描的结果。故障会停止接收后续任务并保持已发事务的排空规则。

这些机制共同减少访存等待和写回空泡，并通过完整帧发布与显示交接保持图像更新的一致性。

## 时钟与时序

[时钟报告](https://github.com/zhang-yl24/fpga-distortion-correction/blob/8e88b3962fc03ca20c92761720f41ab886d3d34c/delivery/20261104-a266044d-timing-review/raw/report_timing_clock_summary.db)给出 core/DDR 用户时钟 125 MHz、输出像素时钟 148.5 MHz、输入时序分析包络 150.2 MHz，以及独立诊断时钟 27 MHz。

现场 a266 版本的最终 ADF 为 `8de179b8c4e620d2f9a5baff70287aa2d8126fb6fada90caeb9975a054be35a9`。[a266 原始时序分析](https://github.com/zhang-yl24/fpga-distortion-correction/blob/8e88b3962fc03ca20c92761720f41ab886d3d34c/delivery/20261104-a266044d-timing-review/README.md)及[慢角 setup 原始表](https://github.com/zhang-yl24/fpga-distortion-correction/blob/8e88b3962fc03ca20c92761720f41ab886d3d34c/delivery/20261104-a266044d-timing-review/raw/report_timing_slow_setup.db)记录：

| 检查范围 | 最差裕量 | 失败端点 |
| --- | ---: | ---: |
| 慢角 DDR PHY setup | −0.032 ns | 4 |
| core 同域 setup | +0.021 ns | 0 |
| 输出像素域 setup | +0.073 ns | 0 |
| 输入像素域 setup | +0.435 ns | 0 |

四条负裕量分别为 −0.032、−0.023、−0.012、−0.006 ns，总负裕量 −0.073 ns，均为 DDR PHY 内部路径；其余 11 个角点/检查组合报告零违例。因此，a266 的现场 30 FPS 结果与仍需收敛的四条物理时序路径同时保留。

后续 KEY1 版本来自 `8c3fe2a05ae56e3338a495f5085d489506352439`，位流 SHA256 为 `cf9fcf563f7487bafccf083f5ad83f7e94c18759beea3236187e32c8b2c66731`。其[KEY1 十二项 STA](https://github.com/zhang-yl24/fpga-distortion-correction/blob/8c3fe2a05ae56e3338a495f5085d489506352439/delivery/20261104-op-camera-key1-raw-corr/bits/STA_12_CHECKS.csv)记录慢/快角 setup、hold、recovery、removal、最小脉宽和 skew 共 12 项内部检查零违例，最差 slow setup +0.009 ns；详见[KEY1 位流身份](https://github.com/zhang-yl24/fpga-distortion-correction/blob/8c3fe2a05ae56e3338a495f5085d489506352439/delivery/20261104-op-camera-key1-raw-corr/bits/BIT_IDENTITY.json)。该结果属于新增 KEY1 的另一份构建，外部 IO、复位和完整 CDC 需按各自资料继续核验。

## 公开资源基线

同一核心架构的 O/P 基础构建（位流 `99f8a734…`）公开了以下资源数据，出处为[O/P 资源记录](https://github.com/zhang-yl24/fpga-distortion-correction/blob/1b9727e31f690a2598ab51cdb27ba645c0d5eda5/delivery/20261103-hdmi1080-demo-source/stable30-OP/STATUS.json)。该表用于架构资源参考；a266 摄像头诊断构建的独立资源表尚未公开。

| 资源 | 使用量 / 容量 | 占用率 |
| --- | ---: | ---: |
| LUT | 30,952 / 66,600 | 46.47% |
| FF | 25,952 / 133,200 | 19.48% |
| DRM | 28.5 / 155 | 18.39% |
| APM | 56 / 240 | 23.33% |
| IO | 144 / 300 | 48.00% |

## 源码阅读与重建

预取缓存、帧处理、DDR 写回和 KEY1 控制核心均可阅读。对诊断构建的 149 项输入，本地已找到 133 项原始 SHA 相同的 Git 对象，另有 10 项经核验的 include 路径重定位导出。精确重建仍缺以下 6 份匹配 SHA 的依赖原件：

`bringup_pll.v`、`iic_dri_cfg100_reset.v`、`ms7200_1080p30_ctl.v`、`ms7210_ctl.v`、`ddr-ip-clock-relations.fdc`、`vendor-ddr.rcf`。

本次技术分析直接使用封存源码与对应时序报告，没有在本地重新构建。后续重建需补齐上述匹配依赖，并将新结果与实际使用的工具、约束、ADF 和位流身份重新绑定。
