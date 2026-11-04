# 仓库新增吞吐分支：本轮增量审查

2026-11-02T20:05Z刷新官方GitHub：main仍为`0408eca0`，没有PR21之后的新main提交；新增 `codex/hdmi1080-throughput`，head **`bdaf8c1527fb46cc5b8753415fa02f464a8c08b0`**（18:35:48Z）。提交账号为codex，不据此猜测具体同学身份。该分支承接我们`2263444c`交付截面，尚未合入main。本轮重点是它的新吞吐/资源结果，而非重复HDMI直通PR21。

[分支交付说明](https://github.com/zhang-yl24/fpga-distortion-correction/blob/bdaf8c1527fb46cc5b8753415fa02f464a8c08b0/delivery/20261103-hdmi1080-throughput/README.md)；[处理引擎报告](https://github.com/zhang-yl24/fpga-distortion-correction/blob/bdaf8c1527fb46cc5b8753415fa02f464a8c08b0/delivery/20261103-hdmi1080-throughput/evidence/engine-summary.json)。该提交的 [吞吐检查](https://github.com/zhang-yl24/fpga-distortion-correction/actions/runs/41502104363) 与[既有工程检查](https://github.com/zhang-yl24/fpga-distortion-correction/actions/runs/41502104375)均成功；CI不等于硬件验收。

## 这次新增的有效信息

`33031f4`加入raster双512B写回缓冲与32bit parity RAM打包、scatter32→16；`0b6fd18`修复跨平台路径/身份检查；`da2d024`补原生依赖恢复/有界整机构建；`bdaf8c1`补三版完整Map/PNR/双角STA/诊断bit回执。

报告采用1920×1080、Penn、零旋转、Gamma OFF、纯校正、预装源与确定性行为DDR压力。未建模视频采集/显示及相应DDR仲裁。

| 隔离引擎模型 | 周期/帧 | 125MHz换算 | 相对baseline周期减少 |
|---|---:|---:|---:|
| baseline | 3218541 | 25.748328ms | — |
| writer | 3072277 | 24.578216ms | 4.54% |
| cache | 2958045 | 23.664360ms | 8.09% |
| both | 2814828 | 22.518624ms | 12.54% |

四组各2073600像素/遮罩与参考匹配，CRC均`4be2b2a6`，输出SHA均`0af8395dd02ae0e56230dc831521f45303f529144c6a61b2b34123c1cef2b812`。fill数16200不变，scatter518400→259200周期；writer输入停顿161488→0。组合44.41fps只是该隔离模型容量，**不是板上新校正帧率**，22.52ms也不是E2E；仍高于60fps所需16.67ms。

三版完整工程Map资源/最终slow setup：baseline FF21898/LUT17066、62条/−0.659ns；cache FF21964/LUT17162.5、155条/−0.762ns；both FF26418/LUT18292.5、16条/−0.619ns。DRM均19.5、APM69、IO144。它们均为诊断候选，仍有DDR recovery/removal及外部IO缺项、未上板，不套用到我们DMA5/PGSTAT/Gamma/rotation构建。

## 对当前1080p60与降资源工作的实际价值

1. **cache宽字打包优先作为资源效率对照。** 独立cache DRM10.5保持，LUT1294→1370、FF1021→1086，用小增量减少scatter一半。应在当前DMA5/PGSTAT及新K/D下做同源比较，不能将旧模型16200 fills固化为所有输入分布。
2. **writer双缓冲证实能消除收集/写回空泡，但FF代价显著。** 独立writer FF4704→9153、LUT1475→2852，缓冲未推为DRM；组合整机相对其baseline增加4520FF/1226.5LUT。若目标同时降资源，应优先评估当前overlap writer的RAM推断/局部命令组织，而不是把旧FF双缓冲直接合入。
3. **D256仍需自己的完整证据。** 当前本机D256/compact/overlap路径与这个分支的16拍scatter不是同一实现；小系统、原生1080、容量和最终STA尚在推进，不据该分支12.54%收益宣称我们的D256或60fps完成。
4. **时序建议必须与当前闭包对账。** 其报告针对自己的cache有效位反馈、FIFO lookup和显示CE路径，保留真实8ns跨域诊断界限；我们的DMA5、private-valid、completion CRC候选已走各自验证，不能叠加旧建议或搬运其具体端点例外。

本次只读取并提炼原始分支报告、源码变更范围与CI状态；没有重新执行它的四组RTL或EDA，也没有将该分支合入生产或本交付。性能比较只用于安排下一个受控实验。
