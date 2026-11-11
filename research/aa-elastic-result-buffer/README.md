# AA 三结果缓冲：原生输入准备包

**SOURCE-ONLY RESEARCH；不可烧板；未运行新 PDS/Map/STA。** 通用系统的 `ENABLE_ELASTIC_BUFFER` 默认 0，现有 AA 冻结候选保持不变。独立入口显式选择 `ENABLE_ELASTIC_BUFFER=1`、`RESULT_BANKS=3`。目标仍是 HDMI 摄像头 1920×1080、标称 60 Hz，KEY1 RAW/CORR、固定 Rational Brown、Gamma OFF、无新增旋转。输入/扫描 Hz 不等于新画面 FPS。结果槽使用 DDR UI 地址空间中的逻辑帧平面，不等于独立物理 DDR bank；板上可用容量、地址解码和写后读可见性仍需验证。

本目录仅发布 11 个新编写的 RTL/遥测文件、板级入口补丁、原生输入准备/检查工具、相对路径与哈希元数据、简要模型证据。目录内 `.gitattributes` 保留这些哈希输入的原始换行字节。**不含任何 164 文件基线源码正文**，也不含厂商 PLL/IP、许可证、工具、位流、ADF 或摄像头像素 oracle。原有版权和合法使用条件仍适用于使用者提供的私有输入。历史输入计划中的 FIRST_PARTY 或 83 项分组只是暂存路径分类，曾包含厂商 bringup_pll，不能据此称为自由分发源码；全部 164 个上游文件正文都保持 seed-only。

## 先准备合法的精确输入

需要同一原生 ON 构建记录中的：

- `native/`：精确 164 文件。仅同名、同参数或新生成的类似 IP 不足以通过哈希门禁。
- 与 `native/` 同级的 `NATIVE_SOURCE_MANIFEST.json`、`MAP_PREPARED.tcl`、`inputs/KEY1_ONLY.fdc`。
- Python 3.10 或更新版本。可选系统静态展开需要已有可信 Icarus 编译器，不会下载或安装工具。

准备器读取真实私有清单中的源前缀，仅做已固定哈希的 include 路径规范化。然后应用有逆变换核对的三处板级入口替换，输出精确 **174 个私有 native 文件、85 个有序导入和原约束**。所有源身份、ROM、约束及输入清单均检查。它拒绝缺失/更改/多余文件、符号链接、路径穿越、已有输出和与源/本包重叠的输出目录。`python -O` 不会关闭这些检查。

在本目录运行。以下 `/data/...` 仅为 Linux 绝对路径格式示例；请换成真实的绝对路径，不要使用 `..`。Windows 应换成对应磁盘上的绝对路径。输出父目录和测试工作目录须已存在，输出目录须全新：

```text
python -B check_public_bundle.py
python -B prepare_native.py --native /data/licensed-build/ON/native --dry-run
python -B test_native.py --native /data/licensed-build/ON/native --work /data/private-test-work
python -B prepare_native.py --native /data/licensed-build/ON/native --out /data/elastic-private
```

输出属于**私有衍生工程，禁止上传整个输出树**。`IMPORT_PLAN.json` 记录器件、顶层、85 导入、include 目录、约束、ROM 运行目录及已观察的 PDS 命令结构。它是输入计划，不是已执行 PDS 脚本。按原合法 PDS 2025.2 build 211867 环境及对应 IP 的官方流程，在新输出目录完成 compile/synthesize/Map、布局布线、独立 STA 和 bitgen，逐项核对真实报告。缺厂商工具/原语时必须停止，不得加空模块或借旧时序结果。

可选静态展开命令，在上面的准备命令末尾加 `--iverilog` 和可信本机编译器路径。它仅以固定原生参数展开真实弹性系统及捕获/DMA/Run8/读出模块，不执行仿真，不展开板级 PLL/DDR 厂商原语，不等于 PDS TOP 完整编译。生成的仿真二进制核验后删除。编译结果、告警数和私有文件摘要仅保存在私有输出。

## 模型证据和本目录的边界

`MODEL_EVIDENCE.json` 是既有完整相机模型证据的摘录，源证据哈希及摘录依据均保留。本轮发布准备没有重跑完整仿真，也没有改动 RTL 或旧证据。

既有完整模型将归一化摄像头光栅送入真实捕获/DMA、共享写端、Run8、读端/FIFO/扫描：4 帧完整捕获/处理/发布，3 帧 CORR→RAW→CORR 扫描，repeat/blank/no-grant/fault 均为 0。运行耗时 92.99 秒，模拟时间 83.274 毫秒，不是板上持续运行时间或端到端延迟。内容相同、理想 DDR 可见性/时钟等限制，以及最后第 5 帧捕获仍在进行、不是全局 drain，见证据中的完整限制。

**本薄包不提供 102 输入完整相机回放。** 重放那项证据需要另行取得完整 fixture-bearing 公共安全包 `aa_elastic_public_source_replay_v2_20261111.zip`（SHA256 `c7a46530720a7e2d9699611572fa5c6c3cc859887a0bbf0009d2647065b2ce6b`），再合法提供精确私有 seed。薄包没有像素 oracle、相机测试台和完整回放 CLI，不能当作免依赖全测试工程。

新 PDS、综合、Map、布局布线、STA、物理资源、位流、实体 KEY1、真实摄像头持续 60 新帧/秒和端到端延迟均未验收。44.96 fresh FPS / 60.01 scan / NNNR 现场观察尚未绑定已确认的同版位流/日志，不能证明本候选性能。保留 AA `87cf6ca4` 默认候选及其原始路径，任何新实现都需自己的完整身份、时序和实板结果。
