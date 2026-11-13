# 1080p 摄像头＋KEY1：三结果槽实验 A（2026-11-13）

**2026-11-13状态更新：团队反馈本次上传版本“验证成功60帧”，现记录为团队报告的1080p60新校正画面实板成功。** 新的原始UART、精确统计窗口和长期稳定数据尚未随反馈归档，不能编造精确小数FPS或测试时长。本目录位流与ZIP身份不变，继续保留可复核的测试步骤。 之前用户报告过 44.96 个新校正画面/秒、约60.01Hz扫描和“三新一重”，但未提供当时位流SHA或原始UART；不能把该观测自动绑定给新旧任一包，也不能将扫描Hz当新画面fps。

新实验保持 1080p60 摄像头输入目标、KEY1原始/校正切换、Brown校正、GammaOFF，采用三结果槽缓冲。无新增旋转，不包含后续 single-beat B 或 owner C 候选。核心标称125MHz，显示148.5MHz。请保留已成功旧位流，只对同型号开发板、原相机/镜头进行实验性易失SRAM下载，不替换永久启动镜像。

项目成果、基础/提高任务、当前资源及历史旋转/Gamma的区别见[仓库总览](../../README.md)。历史功能没有并入本次GammaOFF、旋转0°的位流；历史包内“未板验”等文字保留其生成时点，不回写二进制包或旧身份。

## 下载与文件身份

两包需要配套下载，不要套用旧062c79b7遥测profile：

- [物理位流、33个源码/构建辅助文件及构建记录](delivery-20261113-result3-a.zip)：1,698,925字节，SHA256 `0a50c07a6cc127e186eeea80188cb5b1356d881894c8a06b2569c982f9e67557`。
- [9abf8895专用slot2遥测host与中文步骤](FPGA-9abf8895-Slot2-Telemetry-Host-20261113.zip)：94,302字节，SHA256 `c4c4dd5dfa071dd85ef2707d566f3472b0b6a3029752306e636b3880aaf7a043`。
- [文件校验清单](SHA256SUMS)和[离线校验器](verify_delivery.py)。在本目录运行 `python -B verify_delivery.py`，不需要PDS/串口/开发板。

物理包内下载文件：`bitstream/aa-result3-camera1080p60-key1-9abf8895.sbit`，3,791,112字节，完整SHA256：

`9abf8895212af90b5c55c7fcdc442c6a75cc425187be69a8511bbd16aff6663a`

两ZIP均保持原审查版本字节不变。原物理包 `BUILD_IDENTITY.json` / `README_zh.md` 中“新profile尚待补齐”是生成位流时的历史状态；本目录另附随后完成的专用host补齐此项，不回写历史身份文件。

## 同学最短测试流程

1. 下载并解压两ZIP。先看物理包 `README_zh.md` 和host包 `slot2_service_host_20261113/README_zh.md`。host需Python3.10+；仅现场采集另需pyserial。
2. 在host包根目录检查实际收到的位流文件：`python host/check_bitstream.py "实际路径/aa-result3-camera1080p60-key1-9abf8895.sbit"`。必须命中上述完整SHA。文件SHA检查不能确认FPGA已加载什么，操作者仍需在PDS Programmer中确认选中的就是该文件。
3. 按已有同板流程下载至易失SRAM。先检查出图、校正效果、KEY1两个稳定状态，记录相机真实输入模式/频率。不开Flash烧写，不因出图即宣布通过60帧。
4. host根目录运行 `python run_validation.py`，应66项通过。关闭其他串口软件，确认实际COM端口；每次采集前外部建立干净复位/安静包边界，按KEY1设定稳定CORR或RAW。工具不复位、不烧写、不切KEY1、不清空接收缓存。
5. CORR短测命令如下，COM5、输出目录和epoch标签按现场填写，目录必须不存在。采集期间不切KEY1、不复位：

```text
python host/aa_capture.py --profile run8-elastic-result3-slot2-9abf8895 --port COM5 --out-dir slot2_corr_01 --epoch-label board_corr_reset01 --mode corr --loaded-bitstream-sha256 9abf8895212af90b5c55c7fcdc442c6a75cc425187be69a8511bbd16aff6663a --confirm-clean-reset-boundary --seconds 60 --stats-interval 0.271
```

6. 仅在独立确认采集期间未复位/换模式后运行：

```text
python host/aa_measure.py slot2_corr_01 --profile run8-elastic-result3-slot2-9abf8895 --confirm-uninterrupted-epoch > slot2_corr_01_report.json
```

7. RAW对照需另建一次干净边界，另用输出目录/epoch，改成 `--mode raw`。短测正常后再做独立300秒CORR窗口及KEY1稳定窗口，方法相同（`--seconds 300`）。失败/超时保留原始证据，不修改manifest凑通过。
8. 回传完整采集目录（`capture.json`、`camera-uart.raw.bin`）、报告JSON、实际加载sbit SHA、相机频率和画面/KEY1现象。重点看新呈现fps、重复计数、slot2签名、CRC/遥测丢包/fault，区分少量相机/扫描时钟差重复与固定25%重复。

`presented_fps_nominal` 是新呈现计数率，`processed_fps_nominal` 是处理完成率。旧wire名 `captured_frames` 实际是source descriptor被owner接受数，不是所有相机VSYNC；`dropped=0`不排除无空闲source bank时跳过输入。处理周期仅为采到的最近完成帧样本，不是全体p95，也不等于摄像头到屏幕延时。

本profile把PGSIG001 byte15完整解释为逻辑结果槽0/1/2，不截高位；旧062/default profile明确拒绝slot2。SGK1仍24字节、PGSTAT02仍84字节、PGSIG001仍128字节。profile和完整SHA由操作者声明后严格比对，wire上的静态adfb7264标签本身不认证位流。0.271秒轮询降低1Hz锁相风险，仍不保证每帧采样或无偏。

## 已有证据与后续量化验证

- 真实PDS2025.2 build211867、PG2L100H-6FBG676；本位流由已冻结布线ADF生成，未修改源码或重跑PNR。源commit `22d5b2bc09c0013939de57d47436405a380bb5fd`；构建handoff `ff646832abfebe75bd940024ca7558c03c844580`。
- 路由资源：LUT31,709、FF27,277、APM68、DRM18K6＋DRM36K36（physical grid40）。建模约束下最终内部检查无失败，core setup＋0.109ns、pixel＋0.071ns。不能扩展为完整外部IO/CDC/真实DDR或板级时序保证。
- 最终网表ROM初始化266个有效词逐词核对，padding检查通过。构建、原始/脱敏STA、netlist、ADF与sbit身份见物理包 `BUILD_IDENTITY.json`。本包不含私有网表、ADF或工具许可证。
- host66项纯CPU测试＋独立6项通过，穷举3个profile×256个byte15值。已核37个物理包manifest项、sbit SHA，以及164-file合法私存seed按公开recipe派生的174个native文件/97个payload hash。它们不是板测或独立RTL到位流等价证明。
- 团队已反馈本sbit实板60帧成功；尚未随反馈归档原始UART和精确窗口，完整300秒校正、KEY1独立窗口、光学校正/端到端延时、真实共享DDR吞吐、物理CDC/IO验证仍不能据此全部宣布完成。host包中的4×4小帧旧仿真字节仅做同源码离线重放，不能冒充新1080p实板结果。

## 源码与复现边界

公开源码：[三结果槽候选](../../research/aa-elastic-result-buffer/README.md)；[隔离PDS综合handoff](../../research/aa-elastic-build-handoff/README.md)。物理ZIP也保留对应33个精确公开文件；历史说明中的未运行状态按原日期理解，不改写成后来结果。

**仅克隆公开仓库不足以完整重建。** 需要用户合法持有的精确原164文件 `ON/native` 私有seed、同级manifest/MAP/KEY1记录，以及PDS/器件支持、厂商DDR IP和本机许可证。不得用猜测IP、stub或其他旧top替代。以下只是源码准备/综合入口，不是完整布局布线/位流一键复现：

```text
python -B research/aa-elastic-result-buffer/prepare_native.py --native D:/private/canonical/ON/native --dry-run
python -B research/aa-elastic-result-buffer/prepare_native.py --native D:/private/canonical/ON/native --out D:/private/elastic-native
```

将路径替换为合法本机路径，输出目录必须是新的、位于seed/候选之外。再按构建handoff README的 `prepare / run / collect` 执行隔离综合。该launcher止于synthesis，不包含Map/PNR/STA/bitgen全过程。公开交付没有承诺一键从源码重建相同sbit；任何新实现都须重新核身份、ROM、资源、完整时序及实板结果。请勿公开私有seed、厂商文件、许可证、原始本机路径或网表。
