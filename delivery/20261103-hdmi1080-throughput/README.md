# HDMI 1080p 校正吞吐优化候选

以 `delivery/20261103-hdmi1080-demo-source` 分支提交 `195ae5a313fedc8064408314196090d967c5e81b` 中的真实演示源码为基线。该版本为电脑 HDMI 1080p29.97 → DDR → 原图/校正 → HDMI 输出。`main@0408eca` 的摄像头 1080p60 直通显示属于另一条路径。

交付前已同步该分支的新提交 `2263444`，新增内容为 1080p60 直通路线审查和文档；处理链源码及依赖清单保持相同。

本候选完成两项 RTL 优化、固定模式测量入口和完整 1080p 离线逐像素性能验证。`D:/fpga-build` 下的 baseline、cache、both 三版已完成整机 Map、布局布线、双角 STA，并生成标记为 `DIAGNOSTIC_NOT_TIMING_SIGNOFF` 的 `.sbit`。三版均未下载或板测，仍有 setup 与 DDR 复位时序违规，外部 IO 时序尚未签核；实际纯校正 FPS 待测。构建、资源、时序和位流身份见 [整机证据汇总](evidence/board/summary.json)。基线演示包的 50 项源码校验保持通过。

## 已测得的处理性能

条件：1920×1080、封存 Penn 参数、零旋转、Gamma OFF、固定纯校正、125MHz 周期换算；预装测试源、相同确定性 DDR 背压。包含旋转/Brown 映射、邻域 cache、双线性、Gamma 旁路、结果写回及最终排空。采集、显示与它们的 DDR 仲裁未在此处理引擎测试中建模。

| 候选 | 处理周期/帧 | 换算耗时 | 相对基线周期减少 |
|---|---:|---:|---:|
| baseline | 3,218,541 | 25.748328ms | — |
| writer：写回双缓冲 | 3,072,277 | 24.578216ms | 4.54% |
| cache：宽字缓存 | 2,958,045 | 23.664360ms | 8.09% |
| both：两项组合 | 2,814,828 | 22.518624ms | **12.54%** |

组合模型的处理容量为 44.41 帧/秒，基线为 38.84 帧/秒，提升 14.34%。这些数值用于比较 RTL 处理能力，板上输出 FPS 还受采集、DDR 仲裁、帧缓冲调度及显示约束。

四组各 2,073,600 个输出像素和遮罩逐项匹配独立整数 Brown/双线性参考；CRC 均为 `4be2b2a6`，输出文件 SHA256 均为 `0af8395dd02ae0e56230dc831521f45303f529144c6a61b2b34123c1cef2b812`。缓存填充次数同为 16,200；SCATTER 周期 518,400→259,200，writer 输入停顿 161,488→0。

原始报告与日志在 [evidence/engine](evidence/engine/)，汇总在 [engine-summary.json](evidence/engine-summary.json)。期望像素和输出全文可由测试脚本重生成，原始文件哈希保留在报告中。

## 两项修改及取舍

`rtl/ddr_compact_neighbour_cache_scatter4.v`：两组 parity RAM 从 16bit 改为 32bit 打包，每拍写八个像素，一条 128 像素缓存线的 SCATTER 从 32 拍降至 16 拍；逻辑像素容量仍为 32KiB。同步读后的半字选择与 tag、坐标小数及反压共同保持。模块名和端口沿用演示版。

`rtl/ddr_adaptive_result_writer.v`：raster 路径增加第二个 512B 缓冲，一边接收像素、一边发送上一块 DDR burst。每个完整 bank 提交后再发 AW，保留本地注册写命令、CRC、tag 检查及最终 drain。新增 raster 路径发生错误后停止新事务，已断言 AW/已承诺的 16-beat 事务继续排空，失败帧禁止发布。tile 路径保留封存实现及其既有故障行为。

PDS 2025.2 独立综合结果如下。cache 参数为 WIDTH1920/HEIGHT1080/INDEX7/TAG25；TAG25 来自 24 位像素 tag 加 mask。writer 固定 `frame_tiled=0`，对应此次零角度运行路径。

| 独立模块 | LUT | FF | DRM | APM |
|---|---:|---:|---:|---:|
| cache 基线 → 候选 | 1294 → 1370 | 1021 → 1086 | 10.5 → 10.5 | 3 → 3 |
| writer 基线 → 候选 | 1475 → 2852 | 4704 → 9153 | 0 → 0 | 0 → 0 |

宽字 cache 保持块 RAM 推断；writer 的缓冲综合为 FF，增加 1377 LUT、4449 FF。独立模块结果用于解释结构取舍；完整工程资源和时序见下表。独立模块无正式 FDC/布局布线，不提供时序签核；cache 的孤立 map 因内部总线被视为 647 个封装 IO 而停止，记录保留在 evidence 中。

## 三版完整工程结果

三版的 144 个实际引脚、全部声明电气属性和 11 个时钟均通过审计，位流来自各自 STA 绑定的最终 routed ADF。资源采用原生 Map 报告计数，LUT 包含半 LUT 单位。

| 配置 | FF | LUT | DRM | APM | Slow setup 违规端点 | WNS |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 21,898 | 17,066 | 19.5 | 69 | 62 | -0.659ns |
| cache | 21,964 | 17,162.5 | 19.5 | 69 | 155 | -0.762ns |
| both | 26,418 | 18,292.5 | 19.5 | 69 | 16 | -0.619ns |

三版 fast setup、双角 hold、skew、minimum pulse width 通过；DDR recovery/removal 仍有违规。每版回执的 `physical_timing_accepted` 和 `hardware_release_allowed` 均为 `false`。完整十二类 STA、源码/约束/ADF/位流哈希见 [summary.json](evidence/board/summary.json)。诊断位流生成成功与稳定运行、正式时序签核分别记录。

建议诊断对比顺序：**固定纯校正 baseline → both**，cache 保留为单项优化对照。本次实现中 both 取得最大的离线吞吐改善，setup 违规端点也较少；代价是增加 LUT/FF。三版都需继续收敛时序并取得同条件实板数据。

## 构建与上板交接

见 [BOARD_HANDOFF.md](BOARD_HANDOFF.md)。脚本支持 `baseline/writer/cache/both` 四种独立候选和 `corrected/raw/demo` 三种固定配置。整机构建入口 `build_board_candidate.py prepare` 默认 `cache + corrected`；源码准备工具 `prepare_candidate.py` 默认 `both + corrected`。重建时显式指定 `--variant both --mode corrected`，避免依赖默认值。每份配置按源码生成独立 `param_id`，保留已有 UART 扫描协议。

80 项原生依赖已从本地仓库恢复，逐项通过冻结清单的长度和 SHA256 校验。本地完整包将它们放在解压根的 `native-dependencies/`；包内校验可直接读取该目录，无需 Git 或历史工作区。GitHub 基线目录保留 50 项项目源码及外部依赖清单，恢复脚本、来源记录和使用方式见 [DEPENDENCY_RECOVERY.md](DEPENDENCY_RECOVERY.md)。

`tools/prepare_candidate.py` 接受本地完整包的 `native-dependencies/`，逐项匹配后生成新目录及 Map Tcl；未知依赖、哈希漂移、目录复用均报错。整机 PNR、CDC、外部 IO、双角时序和位流状态以对应候选的构建回执为准。

本候选保留基线约 30Hz 输入/输出配置和封存标定参数。新镜头 K/D 集成后，需用相同参数重跑 A/B；标定会改变缓存访问分布。1080p60 的处理预算为 16.67ms/帧，本次组合模型为 22.52ms，仍有差距。继续推进 60 帧时需评估更宽的像素处理架构、访问调度，以及经整机时序验证的频率；接口时钟、输入准入与显示配置也需一起更新。

## 重现验证

在仓库根目录运行；Python 3.10+，engine runner 需要 NumPy，RTL 仿真需要 Vivado XSim。本次实际使用 Vivado 2017.4。

```powershell
python -B delivery/20261103-hdmi1080-demo-source/tools/verify_package.py
python -B -m unittest discover -s delivery/20261103-hdmi1080-throughput/tests -p 'test_*.py' -v
python -B delivery/20261103-hdmi1080-throughput/tools/verify_delivery.py
```

在本候选目录设置模拟器路径后运行：

```powershell
$env:FPGA_VIVADO_BIN = 'D:/Vicado/Vivado/2017.4/bin'
python -B tools/run_writer_ab.py --work _build/writer-check-01
python -B tools/run_cache_regression.py --workdir _build/cache-check-01 --vivado-bin $env:FPGA_VIVADO_BIN
python -B tools/run_mode_control.py --work _build/mode-check-01
python -B tools/run_engine_benchmark.py --variant baseline --pressure --work _build/engine-baseline-01
python -B tools/run_engine_benchmark.py --variant writer --pressure --work _build/engine-writer-01
python -B tools/run_engine_benchmark.py --variant cache --pressure --work _build/engine-cache-01
python -B tools/run_engine_benchmark.py --variant both --pressure --work _build/engine-both-01
python -B tools/run_engine_summary.py _build/engine-baseline-01/report.json _build/engine-writer-01/report.json _build/engine-cache-01/report.json _build/engine-both-01/report.json --output _build/engine-summary-01.json
```

已执行：writer 25 个场景，cache 4 项基线/候选测试（含完整 1080p），固定模式控制测试，四组完整 1080p engine 逐像素回归，38 项 CPU 测试（24 项 board flow、12 项工具、2 项打包），两个模块的基线/候选 PDS 综合，80 项依赖恢复和无 Git 解压布局校验，以及三版完整工程 Map/PNR/双角 STA/诊断位流生成。详见 `evidence/`；CPU、RTL 仿真、EDA 和实板证据分别记录。
