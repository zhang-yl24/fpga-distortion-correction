# main 8adda884：完整工程包与当前主线身份复核

本复核只读核对 `main@8adda8846f9d3d1f646c5a63d58f128aa786b1cc`、其父 `0408eca0`、所指向的 `bdaf8c1527fb46cc5b8753415fa02f464a8c08b0`，以及本机已封存的 slowAB、D256/key/HEAD 输入。没有推断谁授权了该提交，没有改 main、生产 dirty 工程或冻结输入，没有启动 EDA、烧录或串口。上传工程包不等于竞赛已经提交。

## 新提交增加了什么

`8adda884` 相对 `0408eca0` 仅改根 README，并新增工程包 README、复核回执、ZIP 与 SHA256 文件，共五个路径；没有新增 RTL 优化。工程包源码仍指向原有 `bdaf8c1`。所以没有发现超出前次吞吐分支审查的新算法改动或新板测。

官方链接：[新 main 提交](https://github.com/zhang-yl24/fpga-distortion-correction/commit/8adda8846f9d3d1f646c5a63d58f128aa786b1cc)、[完整工程包说明](https://github.com/zhang-yl24/fpga-distortion-correction/blob/8adda8846f9d3d1f646c5a63d58f128aa786b1cc/delivery/20261103-hdmi1080-board-package/README.md)、[上传者解压复核回执](https://github.com/zhang-yl24/fpga-distortion-correction/blob/8adda8846f9d3d1f646c5a63d58f128aa786b1cc/delivery/20261103-hdmi1080-board-package/delivery-validation.json)。

Git 树记录 ZIP 为 29,947,602 字节、blob `694b7b006ad2eb0d39f4e2889f911cf080d5e391`；SHA 文件声明 SHA256 `3164e3fca394b5a9734438329589ec476ff59b1731cfb7c90fc9084051faec81`。上传者回执记录 497 文件、80 依赖、三版 prepare 与 38 工具测试通过，且 `hardware_accessed=false`、`eda_rerun=false`。

**本任务未重新下载或解压该二进制 ZIP。** 官方 GitHub 连接器支持读取仓库 UTF-8 文件，不提供仓库二进制下载；本次独立核查的是提交树、可在线读取的源码准备记录、实际源码和依赖字节。497 文件解压通过仍归属于上传者回执，不能写成本任务重跑。

## 130 项源码与依赖

三版 preparation 的 130 个路径都与我们 frozen manifest 完全相同；80 项依赖的长度和 SHA256 全部一致，并只读核对了本机冻结依赖原件。另按 `prepare_candidate.py` 的明确 overlay、固定模式和参数 ID 替换规则，独立重建三版各 50 项自有输入，全部 SHA256 匹配；三份完整 candidate identity 也重新计算一致。

| 候选 | 与 slowAB 130 项输入相同 | 改动 |
|---|---:|---|
| baseline | 128 | 固定纯校正 selector、top 遥测参数 ID |
| cache | 127 | 上述两项，加 32bit 打包 cache |
| both | 126 | 上述三项，加双缓冲 writer |

编译副本的 include 路径重定位另列于[机器可读复核](MAIN8ADDA_BOARD_PACKAGE_REVIEW.json)，不误算成算法变更。80 项受限依赖只发布身份比较，没有在我们的增量中重新上传原件。

## 位流身份与实板边界

| 身份 | 参数/模式 | bit SHA256 | slow setup / WNS | FF / LUT / DRM / APM |
|---|---|---|---|---|
| 已板显 slowAB | 原图/校正约3秒切换 | `2793ab0b6f1edb6429cb26b4cc927364cc1c512fe29f7c8b1dd473291374a819` | 35 / −0.579ns | 21936 / 17133 / 19.5 / 69 |
| 新包 baseline | `b0481b1d`、fixed corrected | `8f59217b5873e95a6c4064f69f717b663e3fe3bc3bf92aec1eddf7de8c7ad1bc` | 62 / −0.659ns | 21898 / 17066 / 19.5 / 69 |
| 新包 cache | `1a247c5b`、fixed corrected | `3413cb9b7c59e25b2a238ad1ba842e2b6727f21d7f1c7f21d80a4dc27a3079d3` | 155 / −0.762ns | 21964 / 17162.5 / 19.5 / 69 |
| 新包 both | `f36cb459`、fixed corrected | `cfefb855808ad5370bc6d020debfa6f4c5443c79d8df41df8cfa2a4d0ed57075` | 16 / −0.619ns | 26418 / 18292.5 / 19.5 / 69 |

新包的三个 bit 身份来自其源提交的整机证据汇总；未在本任务中读取二进制重新计算。三版均标记 `DIAGNOSTIC_NOT_TIMING_SIGNOFF`、尚未板测，setup、DDR recovery/removal、外部 IO/CDC 待验收。不能把其 baseline 当作旧 slowAB，也不能把三版中较好的不同指标拼成同一成果。

slowAB 已确认的是电脑 HDMI 1920×1080、29.97Hz 经 DDR 与处理链后实屏切换；60.066112s 窗口有1798扫描签名、1394不同输出ID、404重复。它不是固定纯校正 FPS、摄像头画质或 E2E 证据。[完整冻结状态](README.md)

## 与 D256、key、HEAD 的关系

本任务分别只读验证了三套 native manifest 的全部 **139 项文件哈希**，没有借助名字把它们认作新包的130项工程。

| 本机候选 | Map FF / LUT / DRM / APM | 本机物理记录 |
|---|---|---|
| 原 D256 compact | 38984 / 44338.5 / 22 / 70 | Map通过；原PNR控制器预算耗尽，没有最终route DB，未执行最终STA |
| AREA2 + KEY_PIPE2 | 30261 / 44212 / 26 / 70 | Map通过；3600s路由预算后仍未收敛，无最终route DB/STA/bit |
| HEAD_PREDECODE1 | 30278 / 44944.5 / 27 / 68 | Map通过；此截面未进入PNR，不是已布线时序结果 |

key 在原 D256 后续 area/writer-RAM/ref-ALU 父版上切分选择路径；HEAD 又以 key 为父版，将 FIFO head 解码前移。它们有不同的源码哈希、Map ADF 与资源。HEAD 比 key 增加17FF、732.5LUT、1DRM，减少2APM；不能称面积整体下降。key 的另一次 decongestion2 **place-only** 已成功，只说明放置完成，不能当成 route 或 STA 收敛。

**主集成工程师在本次交接中已报告：原 D256 的1920×1080处理引擎连续3帧达到60fps周期预算，RTL通过。** 这是原 D256 的模型阶段成果，不是 key/HEAD 的原生完整引擎复跑，也不是实板持续60帧。该结论来自主集成回报，本任务未重新运行其云端日志；作者本机 `NATIVE_ENGINE_BENCH_STATUS.json` 的旧准备状态仍保留为 `PREPARED_NOT_RUN`，没有把它改写成执行回执。采集/扫描仲裁、真实DDR、1080p60 I/O/PLL、路由后125MHz及实板持续FPS仍待分别证明。

## 可吸收的最小范围

新提交本身没有比 `bdaf8c1` 多出窄 RTL 优化。此前已确认的两点仍有价值：32bit cache将一条128像素线的SCATTER由32拍减至16拍，独立cache的DRM仍10.5；双缓冲writer去掉模型中161488拍输入停顿，但其独立综合增加4449FF、1377LUT。新包both整机比其baseline增加4520FF、1226.5LUT，不能称资源降低。

建议保留 **cache packing 的窄对照** 与 **writer事务排空/失败帧不发布的验证案例**，由主工程师在实际目标路径评估。D256已有独立runtime prefetch/cache及RAM writer演进，不能直接替换成旧cache/both后继承其60模型结论。移植后必须重新绑定profile并验证完整像素、mask、背压、lease、CRC和时序；本任务没有修改生产RTL。

四组旧模型的baseline3218541→both2814828周期，即25.748328→22.518624ms（nominal125MHz），减少12.543%，对应模型44.41fps。该bench不含采集、显示及共享DDR仲裁。它与原D256三帧60模型是两套不同实现和证据，均不能替代持续实板60。

当前目标仍是新1080p60摄像头经DDR/校正链达到输入与输出60Hz及每秒60个新校正帧，完成setup、复位/IO约束、资源、同源标定画质和延迟验收。GitHub源码交付、诊断bit和CI通过均不是竞赛已提交或基础/提高任务全项通过。
