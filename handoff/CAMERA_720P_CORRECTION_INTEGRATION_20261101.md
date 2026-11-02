# 720p 当前镜头矫正：最小接入清单（2026-11-01）

本轮为独立源码核对和 CPU 尺寸核算，未修改冻结生产 RTL/工具/证据，未运行 PDS、JTAG、UART 或大仿真。真实 VGA/720 配对采图及 K720 验证由主线推进；本文件不提供未经实拍验证的新镜头参数。

## 结论：计算链已存在，缺的是本模式参数和相应验证

当前 camera720_transport_top.v:152-168 已将 13 项配置和 radius guard 送入 camera_vga_video_system。该系统在 rtl/experimental/camera_vga_video_system.v:77 连接 lens1080_bank_core；后者在 lens1080_bank_core.v:50-51 连接现有流水帧引擎并固定 gamma bypass。引擎经 pipeline_gamma_frame_engine_1080_scatter4.v:42-48 进入旋转、bounded_brown_inverse_mapper、scatter4 rowpipe cache 和双线性插值。角度已固定为 0。identity 只是当前参数，不是绕过矫正硬件的另一条数据路径。

因此生产增量原则上仅为新独立 camera720_calibrated_top.v、camera720-current-lens.vh，以及其来源清单/构建适配；共享计算、缓存、DDR、采集、复位和 HDMI 输出 RTL 首轮不变。保留已验收 transport 作为回退。非零系数可能改变综合优化、资源和实际布局，不能继承旧 ADF 时序结论。

## 1. 将实证几何变成明确的模型输入

- 输入应绑定当前 CAM2/镜头、720 模式、原始图像尺寸 1280×720、真实配对图和独立验证证据。若 A 的裁剪/缩放假设通过，可用 K720=A×KVGA、D 不变；否则补本模式标定，不能机械乘二。
- camera720_geometry_transfer.py:109-136 的 candidate 明确不是 drop-in profile：只量化 source K，未验证输出 K、逆焦距、径向多项式或整条 FPGA 算术。不要将它的光学未验收标志改成 true 来迁就旧工具。
- 另选 Kout720，决定矫正后视场/裁剪；K720 是相机内参，Kout720 是输出投影，二者不可混用。先保持 1280×720、0°、gamma bypass。右下物理遮挡和目标模式可见范围须保留，不能继承 VGA 全区域许可。
- 现有原厂寄存器只支持模式变化的合理解释，不能唯一确定精确 A。VGA 5001=a3 启用 scale，720 5001=83；窗口、offset、binning 也改变。2I+(0,-120) 只是假设 1280×960 居中裁成 720 的起点，半像素/取样相位待实拍。方向位相同，当前 720 实屏已确认正立。详见 work/camera720-orientation-crop-review.md。

## 2. 复用现有 fisheye→Brown 参数审计，不直接写 D 到 K1/K2/K3

复用 tools/wideangle_mapping_audit.py:audit_profile（122 起）的纯函数：输入已验证的 fisheye K720/D、显式 Kout720，output_size=(1280,720)、angles=(0,)、stride=1。它重新拟合三项 Brown radial、输出 13 个整数配置及实际所需 radius guard，并用 OpenCV fisheye 坐标和独立整数 oracle 对照。现有核并非四项 fisheye D 的直接执行器。

必须检查全部 921600 坐标：有限值、算术 invalid=0、无折叠、最大坐标误差满足明确门槛、来源边界/双线性邻点覆盖符合所选视场。现工具默认最大误差 0.25 个输入像素；这是数值近似误差，不是镜头标定 RMS 或光学验收。报告必须说明黑边/部分边界邻点策略，不能将默认最低 50% in-bounds 当最终画面品质目标。

该工具的旧 candidate_ready_for_profile_review 还严格要求 provenance=real_chessboard_captures 和旧式来源 flags（230 起）。实测模式转移应保留其真实派生 provenance；新 preparer 绑定单独的实证转移/目标模式验证以及数值 passed，不伪装成重新标定，也不修改冻结旧工具门槛。

从审计报告生成新的 header：13 个具符号的整数字面量、profile/transfer/mapping SHA、重新计算的 MAX_RADIUS_Q22。参考 prepare_camera_vga_calibrated.py:54-64 的格式即可；该 preparer 的 calibration() 固定 VGA 文件、整数和 guard，不能直接用于 720。

## 3. 固定点和存储边界：现有宽度够用，但系数仍须逐帧验证

| 项目 | 现有实现 / 720 要求 |
|---|---|
| 像素位置、主点、源焦距 | signed 24 位、8 小数位，即 Q15.8；范围 [-32768,32767.99609375]。不是 32 位的 Q24.8。 |
| 逆输出焦距 | signed32 Q1.30；须有限、正且量化不为零。 |
| Brown 系数与中间归一化值 | signed32 Q9.22；需检查每一处饱和/overflow，而非只看输入是否装得下。 |
| 归一化硬限 | bounded_brown_inverse_mapper.v:220 对 x、y 各限制 ±2；不能通过加大 radius guard 绕过。 |
| 半径保护 | 同文件:222 检查 r²；审计按本次 Kout 全帧求 max+2。旧 transport guard=8388608、VGA guard=11610104 都不能直接沿用。 |
| 舍入 | 算术为 nearest、ties toward +infinity（mapper:26-30）；生成配置采用现有 oracle quant，不能把浮点四舍五入描述当位精确实现。 |
| 栅格/tag | 最后 u/v=327424/184064（Q8整数）；tag 最大921599，小于24位容量。无需扩位。 |
| 帧存储 | RGB565 每帧1843200字节；57600个256位beat；DDR地址以4字节为单位，每帧460800单位。 |
| bank stride | 1048576个4字节单位=4MiB；不是1MiB。当前四bank布局仍足够，无需为720矫正加bank。 |

本轮已用 CPU 核算1280×720的 WIDTH%16、HEIGHT%8、像素数%256、tag和bank边界均满足 lens1080_bank_core.v:26-29 / pipeline_gamma_frame_engine_1080_scatter4.v:31-40 的条件。具体 Kout 决定的归一化范围和多项式溢出还须等实证参数审计；这里没有提前宣布通过。

## 4. 新候选最小文件与检查

1. 新的目标模式 profile/transfer/heldout 记录与 numerical mapping 报告，绑定实际拍摄来源；不覆盖 VGA。
2. 新 camera720-current-lens.vh 和 camera720_calibrated_top.v：从冻结 transport 派生，仅 module/include/配置名称和说明变化；尺寸、输入403动作、极性、字节序、8×1500ps delay、125MHz核心/现有输出时序、bank/cache结构不变。
3. 新窄 preparer/runner 及 source manifest：复用当前构建逻辑，但校验上述允许差异和本次参数来源。现 prepare_camera720_output.py:43-56/94-101 故意强制 identity；保留它，不能在原 transport header 上直接改数绕过校验。
4. 新校正仿真 runner/testbench 适配，用现有 720 system/control 模板和实际参数，不扩大成新的流水结构。

## 5. 必做验证与现有 identity 测试的具体陷阱

- 先 CPU 全921600坐标对照 OpenCV/整数参考，再用同一新 header 驱动真实 bounded mapper，核对 tag、backpressure、配置仅在 drain 后更新、reset后重新配置；覆盖负径向系数字面量和边界/黑边。不直接运行古老 tb_calibrated_mapper.sv 的硬编码绝对include路径。
- 现 run_camera720_system_sim.py:48 正则只读非负参数，:55/:68 强制 identity；新 runner 应读审计整数或支持负号并核对 header，生成矫正 golden，保留旧 identity 回归不动。
- **CRC必须拆分**：tb_camera720_system.sv:129、:137、:193 对输入commit、处理release、扫描使用同一 expected_crc；runner:141 也要求 commit/release 同 CRC。这只对identity成立。新测试用 SourceCRC 校验capture commit，用 CorrectedCRC校验release/scan，写两份CRC参考，不能放宽真实CRC检查。
- 全系统至少两不同源帧走真实 DVP→DDR→mapper/cache→输出扫描，逐像素对照独立RGB565插值golden，源/结果bank归属、57600beats、frameid、CRC、DDR反压/争用、最后行列和扫描黑边均保留；可在其中加入实际720原图作为第三份模型输入。小图或旧 synthetic stress pass 不能替代本参数全帧。
- 最新完整720 synthetic nonzero stress（run_camera720_output_sim.py:67）已证明同架构能处理非零径向/切向配置；它不能证明本镜头参数正确。新参数完整系统测试通过后再构建独立PDS目标，核对新时序/资源/CDC/IO及复位范围，再生成/下载SRAM并观察实际直线。

先完成720矫正。此阶段不改变cache大小、tile顺序、DDR调度或PCLK，不把仿真周期、HDMI刷新率或UART导出时间当实际处理FPS。矫正实际通过后再依现有 performance plan 测瓶颈。

## 本轮源锚点

- camera720_transport_top.v: b71329fe4621f6a820fbc2b4e2513e51bfc06bed4bf87dd4adea42f78d8c0629
- camera720-identity.vh: 84a8cfc58afc17bed4ee7eae7dcdb90cbe2a7c3edd6d900b52a5b8553435e4a8
- bounded_brown_inverse_mapper.v: d13bad6e4deda11face236f2c8c2c6e91b37075a7de87a33a42bd90f64dd7691
- wideangle_mapping_audit.py: bc4b808a2c2b883220b5d317e443880b89784a82b346ae281068465332571d20
- run_camera720_system_sim.py: 1eeff51d4d2a41c771f069013949356d75ec7b60aaf5fc2874358d718a9589e3
- tb_camera720_system.sv: c91b99f1af686ab524d8aeba320c2b6de50d7579006785e36827577b680906c6
