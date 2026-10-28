# 1080 候选的本机 RTL 复现

本轮接入远端 `890d21e`，并保留已合并的 CI 修复。新增验收记录测试进入 GitHub Actions；离线 RTL 使用本机 Vivado 2017.4，不需要 PDS 或开发板。

## 可复用入口

`run_board1080_rowpipe_unit.py` 和 `run_board1080_system_sim.py`（包含 CDC-reset 包装入口）现在按以下顺序选择工具目录：`FPGA_VIVADO_BIN`、仓库根目录 `team-config.local.json` 的 `vivado_bin`、历史默认目录。相对配置路径以仓库根目录为基准。机器路径和配置文件继续留在本机。

旧 RTL 中四处 include 使用原电脑的 `D:/English/FPGA` 路径。系统仿真入口只在当前工作目录创建编译副本，将这些 include 改为 `relocated-headers/...`，头文件副本保持原字节。这样也避开了旧 Verilog 预处理器不能读取中文绝对 include 路径的问题。原始 RTL 和已封存参数均不修改。

报告记录原始源码、实际编译副本和头文件 SHA256；后续 native 回归使用 small 结果前，会重新计算完整的 include 替换并核对实际文件。删除绑定或修改副本后重写自报哈希都会被拒绝。原有 fresh 目录、预算、源/夹具漂移和同源 small 前置要求保留。

## 本轮验证范围

- 地址流水候选：保留原 64 输出/63 间隔周期测试；新增 32 个变化坐标/分数/TAG 的缓存命中请求、24 个带反压请求、12 个命中/未命中混合请求。独立 scoreboard 检查四邻点、分数和标签，要求真实快慢路径及保持条件均被触发。
- 系统小尺寸回归：32×16、八帧，共 4096 个真实输出扫描像素，覆盖输入 DMA、行为 DDR、SCATTER4、FIFO、逐像素/CRC、bank 复用、故障隔离和共同复位恢复。它不测原生 1080P 帧率。
- CPU：工具配置、绑定头文件路径重定位及篡改拒绝测试；新增验收附件、外部事件延迟和证据分类测试接入 CI。

实际结果、当前源码和原始本机日志哈希见 [本轮结果](../distortion/results/local-rtl-reproduction-20261028.json)。原始完整运行目录保留在 `distortion/build`，不作为普通 Git 源码附件发布。首轮原机 include 缺失和第二轮中文绝对 include 编译失败的目录也保留，不把失败日志改写为通过。

## 重跑地址流水单元

以下命令从仓库根目录执行，先安装 `requirements-team.txt`，并配置本机 Vivado 路径。每次选择新的工作目录，不能覆盖已存在的结果：

```powershell
New-Item -ItemType Directory distortion/build/rowpipe-team-check
.venv/Scripts/python.exe distortion/tools/run_board1080_rowpipe_unit.py `
  --workdir distortion/build/rowpipe-team-check --maximum-seconds 180 --execute
```

不传 `--execute` 时仅生成计划。180 秒为编译、展开、仿真的共享预算；超时后的自有进程树清理另有有限等待。

## 重跑系统小尺寸回归

原始生成器 CLI 用于原生 1080P；small 使用已有 CPU 测试 API，明确指定 `_test_size=(32,16)`。在 `distortion/build/offline-20261024` 的新子目录分别调用 `generate_1080_core_vectors.generate_vectors`，生成 variant 0/1；再用下列 CLI 生成三种独立源图的序列。`<sequence-dir>` 必须是已创建的 `distortion/build/offline-20261024/continuous-input1080-20261027-a` 子目录。

```powershell
.venv/Scripts/python.exe distortion/tools/generate_continuous1080_vectors.py `
  --vectors0 <small-vectors0/vectors.json> --vectors1 <small-vectors1/vectors.json> `
  --output-dir <sequence-dir> --maximum-seconds 60
.venv/Scripts/python.exe distortion/tools/run_board1080_cdc_system_sim.py `
  --mode small --workdir <fresh-workdir> --sequence-dir <sequence-dir> --maximum-seconds 300
```

`<fresh-workdir>` 必须是已创建的 `distortion/build/board1080-cdc-reproduction` 空子目录。该入口执行实际 RTL。原生 1920×1080 八帧回归耗时较长，本轮没有重新运行；其同源 small、原生序列及预算要求仍然有效。

地址流水候选仍与主链隔离，尚无整板时序或实板性能结论。DDR recovery 每角 245 项失败、外部 IO/CDC 及真实镜头输入/标定仍需继续解决。
