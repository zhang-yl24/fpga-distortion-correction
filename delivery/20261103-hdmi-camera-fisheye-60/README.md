# 1080p60 鱼眼校正技术路线集成候选

基于同学已上板的 `delivery/20261103-hdmi-camera-fisheye-c`，保留真实 OpenCV fisheye 标定、RGB565 帧存、双线性插值、边界处理、零旋转和 Gamma OFF。目标为每秒 60 个新的 1920×1080 校正帧。原 C 版及原有资料保留。

本候选已完成 RTL 集成与数字仿真。**当前物理时序尚未收敛，实板 60 FPS 尚未达成验收；本次交付为源码候选，未生成新的 60 FPS 位流。** 交付状态与证据绑定记录在 `VALIDATION_STATUS.json`。压缩包保留的原 C 版位流属于已上板的约 4.28 FPS 基线。

## 功能和修改

- 缓存每次直接接收 8 拍 DDR 数据；四邻域地址和边界提前计算，同步读取缓存元数据。
- 采用 8×8 输出分块，两路分别处理前 640 行和后 440 行，仍按完整 1920×1080 标定计算全局坐标。双 stripe 将输出恢复成连续光栅次序，乒乓 burst 缓冲并行接收像素与写回 DDR。
- 上路使用 256 KiB、源行对齐的缓存索引；下路使用 128 KiB 线性缓存。真实 DDR 地址、缓存行大小和像素算法保持一致。
- DDR 返回的 data、valid、last、ID 整束寄存，保留事务归属与异常检查。新增描述符启动寄存、两项 RGB/tag FIFO、写回局部地址寄存和显示末帧校验流水；固定使用寄存返回的路径单独配置，缩短接收控制路径。
- 使用三个源槽与描述符队列；HDMI 输出跟随约 148.5 MHz 输入像素时钟，实现 2200×1125 的 60 Hz 扫描。单独统计新帧、重复帧与空白扫描。
- 保留厂商 DDR 约束与优先布线，核查 IP 版本和实际约束范围；为 CA 组合信号增加精确 fanout 属性，已核对综合后的复制逻辑等价性。
- 使用 PDS 原生同步器属性，保护跨时钟域两级触发器，并核验最终布线网表中的连接，避免同步链被综合为移位寄存器。
- 缓存地址与写回 beat 控制采用局部扇出复制；缓存索引采用头尾寄存器，显示位置提前译码，完成描述符在发布前私有预取。各项修改分别核对功能与时序。

图示路线对应说明见 `docs/IMPLEMENTATION_ROUTE.md`，上板步骤见 `docs/BOARD_ACCEPTANCE.md`。

## 完整帧数字仿真

以下为 125 MHz 引擎和明确定义的 DDR 共享服务压力模型。真实板卡带宽和新显示帧率需要实测。

| 测试 | 完整帧周期 | 每帧耗时 | 模型处理速率 | 像素差异 |
| --- | ---: | ---: | ---: | ---: |
| DDR 首拍延迟 12 周期，带争用 | 1,692,988 | 13.543904 ms | 73.834 FPS | 0 |
| DDR 首拍延迟 40 周期，带争用 | 2,076,702 | 16.613616 ms | 60.192 FPS | 0 |

每帧均验证全部 2,073,600 个像素、无重复/遗漏写回和正确帧身份；CRC32 为 `04f1ed35`。与未调整索引的双路 128 KiB 配置相比，填充从每帧 31,147 次降至 23,295 次。高延迟模型相对 60 FPS 周期预算仅余约 0.318%，板测需要关注实际 DDR 竞争和重复帧。

真实链路小帧整机测试覆盖采集 CDC、三源槽、DMA、两路校正、写回、显示和复位：两个运行阶段累计 32 个唯一显示帧（12 原图、20 校正），151,552 个显示像素逐一核对，欠流和像素不匹配均为零。小帧采用尺寸适配的缓存索引与行分割；原生 1080p 配置由上面的全帧测试覆盖。

以上数据绑定交付 I 阶段：`evidence/final-i-lat12`、`evidence/final-i-lat40` 和 `evidence/system-final-i-rowpad640-fanout16`。原生构建源码身份为 `d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5`；仿真闭包已与该构建逐文件核对，仅归一化绝对 include 根路径。各阶段 evidence 目录保留诊断过程，分别绑定当时源码。

原生布局布线与时序报告保留 slow/fast 两个角的 setup、hold、recovery、removal、脉宽和 skew 检查。同步器结构核验、精确路径约束、HDMI 外部 IO 和实板测试各自记录，编译完成本身不代表物理签核。

## 物理实现结果与剩余工作

I 阶段完成 PDS 综合、映射、布局布线和时序分析。slow setup 最差裕量：核心域 −2.886 ns、输入/输出像素域 −2.414 ns、核心到 DDR PHY0 −0.012 ns、配置时钟到板载参考时钟 −0.331 ns。完整失败端点与各类检查保留在 `evidence/physical-i/timing.json`。后续需继续处理缓存有效元数据选择、错误/复位控制扇出和物理布局，再生成并验收新位流。

本轮已通过的物理子项包括：FIFO 的 34 条两级 Gray 同步链及其它存活同步链的实际触发器/连接核验；两个角全部 34 条 Gray 数据路径和 4 组 skew 的 6 ns 边界检查；厂商 DDR 约束审计；缓存地址与写回 beat 局部复制的逻辑/连接等价。局部改善尚未形成整机时序收敛。仍需完成 held-bundle CDC、复位、外部 IO 与实板长时间测试，详见 `docs/CDC_USER_PATH_AUDIT.md` 和 `docs/BOARD_ACCEPTANCE.md`。

## 构建身份与复现

选定配置为 `rowpad`、8×8 tile、640/440 行分工，启用 `--ddr-fanout16`。交付配置 BuildID 为 `11037003`，ProfileID 为 `ed59f83e3cfbc77b`。未启用该属性的默认开发配置 BuildID 为 `11036003`；串口接收程序需明确选择实际 ID。

完整仓库中，从本目录运行：

```powershell
python tools/prepare_candidate.py --output D:/f60-build --ddr-fanout16
& '<PDS-install>/bin/pds_shell.exe' -file D:/f60-build/build.tcl -work_dir D:/f60-build -project_name hdmi_camera_fisheye_top
python tools/run_engine_full.py --work D:/f60-sim --pressure --read-latency 40 --ddr-fanout16 --vivado-bin '<Vivado-install>/bin'
python tools/run_system_contention.py --work D:/f60-system --ddr-fanout16 --vivado-bin '<Vivado-install>/bin'
```

使用新的短路径输出目录。准备脚本逐文件校验原 C 版依赖，再应用本候选覆盖文件；完整帧脚本从封存的标定头文件和径向表生成独立整数参考。Python 需安装 NumPy，串口采集需 pyserial。本轮使用 PDS 2025.2 ADS build 211867 和 Vivado XSim 2017.4。

ZIP 内提供仓库目录结构及 `native-source/` 自包含冻结工程。无需原仓库即可运行：

```powershell
python native-source/rebuild.py --verify-only
python native-source/rebuild.py --output D:/f60-rebuild
```

重定位脚本校验全部 116 个编译输入、IDF 依赖、include 路径和 Tcl，输出新目录及 SHA256 清单。编译器和器件支持需单独安装。包内 `delivery-manifest.json`、候选清单与压缩包 SHA256 用于核对交付身份。
