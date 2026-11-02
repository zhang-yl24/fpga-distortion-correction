# 同学新上传 1080p60 HDMI 摄像头版本：追加审查

2026-11-02T16:32Z 刷新官方 GitHub 后确认：[PR #21](https://github.com/zhang-yl24/fpga-distortion-correction/pull/21) 已在16:29:02Z合入。源码提交 **`214cc2ece823737d384d68350f6b5679c18c210b`**，合并main **`0408eca0fe727763da0077d35e9daa54f5313ad3`**；此前本包关于“最新为720p”的初审仅适用于旧c81898c0。新main的 [CI 41481913101](https://github.com/zhang-yl24/fpga-distortion-correction/actions/runs/41481913101) 已成功。

## 确认了什么

新版本是 **新 HDMI 摄像头 → MS7200并行RGB888 → 同步采样一级 → MS7210 → 显示器** 的源同步直通。不是CAM2 DVP，也没有DDR、缩放、frame store、Brown校正或Gamma。

- `distortion/board/hdmi_camera_direct_top.v`：`assign pix_clk=pixclk_in`，所有27路RGB/HS/VS/DE来自同一采样级；ready只控制DE，不门控转发时钟。默认`INPUT_TIMING_CONFIGURED=0`保持黑屏，实际构建副本唯一改为1。
- `distortion/rtl/experimental/hdmi_camera_pixel_sampler.v`：同一PCLK上采样完整27bit bundle，局部复位两级释放，valid立即屏蔽停钟时保留的数据；第一有效样本建立历史，不凭复位值制造边沿。
- `distortion/board/hdmi-camera-direct-internal.fdc`：输入150MHz/6.6667ns包络，输出clock为输入divide-by-1，只有10MHz配置PLL，无独立视频PLL或DDR。新目标69pins，不能复用为我们144pins的最终约束。

[封存入口](https://github.com/zhang-yl24/fpga-distortion-correction/blob/214cc2ece823737d384d68350f6b5679c18c210b/distortion/results/hdmi-camera1080-direct-display-20261102-a/README.md) 包含实际源码/编译副本、位流身份和原始回执。记录中的SRAM/DONE/器件ID通过、Flash未写；用户在镜头前移动后确认画面稳定。位流SHA `33aca64d692778a9ba316828c32b9b816a0878de701e8e7fd4febcc703335156`，ADF `2c88e0d98fee65326afbea25ae2282e0a182a7a0becbc5baf434da36dd84287f`。

原始raw-v2同输入源的19个有效守恒窗口记录：PCLK估计 **148501164.6316Hz**，VS上升/下降各60Hz；行周期2200 PCLK，VS周期2475000 PCLK；DE高宽1920、active lines1080；VS高宽11000 PCLK（5行）、低宽2464000（1120行）。VS/DE选择正有效，HS极性、RGB精确格式、外部AC和频率物理校准仍未验收。direct固件自身无UART；不能把前驱raw-v2的测量写成direct版本新遥测。

记录的direct最终双角十类内部STA通过，但外部AC/RGB像素精度标志仍false；它没有校正引擎，因而**不能证明60个新校正帧/秒，也没有独立光学唯一FPS、镜头标定或端到端延迟结果**。本次审查对9项源码快照及6项gzip原始记录完成压缩/解压后哈希核对，未重跑其完整portable包、EDA或硬件。

## 与我们相比，最小可复用点

1. **直接采用已测输入profile作为新摄像头适配候选依据**：1080/1920/2200/1125/60Hz、正VS/DE、约148.5MHz。主工程的73500..75000 PCLK热身窗口和74.25MHz输出仍是30模式，须独立60 profile；不能把strict/report-only报警直接隐藏。
2. **无需凭空寻找新TX“60Hz寄存器表”**：本次逐项核对发现，同学TX49条命令与我们的TX49表地址/数值/顺序全部相同，RX311条也全部相同。256字节EDID完全相同且两块checksum为0，preferred DTD仍 **74.25MHz/1920×1080（FPGA1080P30）**。这说明该摄像头实际在现有初始化下输出了60Hz；不证明EDID已升级60或所有HDMI源均如此。需要面向其他源时仍应设计/核验真正60 profile。
3. **采样器只借用缺少的reset/valid/首样本契约**：我们的`hdmi_rx_sample_bank.vh`已经是27bit同拍单级采样，不应再次叠加一级。若引入其模块，应替换原一级、统一observer与DMA输入来源，并重新检查复位/停钟/帧头。不要将其direct转发clock直接替换DDR结果扫描clock。
4. **保留direct为独立无DDR对照路径**，用于区分新相机/PHY问题与DDR/校正问题。不能把其小资源/一采样级延迟或十表通过当作主校正引擎成果。

我们raw也已核为几何identity：`sample_x=in_u`、`sample_y=in_v`，绕过Brown及rotation，完整1920×1080窗口；没有720p提示的“清零K/D后保留zoom”问题。当前交替模式仍来自不同source帧。同源定量对比需保存源/结果像素及真实K/D、mask，或为冻结源的双view设计独立source/pair ID与递增result ID；现扫描协议拒绝相同输出ID却不同bank/CRC，不可简单重放同ID。

本次只提交事实更新与复用建议，不合并同学RTL、不改生产工程。具体摄像头型号/镜头K/D与我们的新校正构建，仍由主工程后续核实和验证。
