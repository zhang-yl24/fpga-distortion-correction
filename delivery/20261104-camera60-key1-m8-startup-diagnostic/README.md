# 摄像头＋KEY1＋M8＋启动对齐：诊断候选

状态：DIAGNOSTIC_TIMING_UNCLOSED_NOT_BOARD_TESTED。
仍有 1 条 slow setup 违例，WNS -0.007 ns，其余11项内部检查无违例。
此位流可能不稳定，未在同学摄像头上验证，不是最终签核版。

变化：M8写回结构；安全bank完成/显示请求同拍交接；首次结果就绪后启动输出扫描。
保留摄像头输入配置、KEY1、运行时Gamma/旋转以及PGSTAT02。
不使用电脑作为产品视频源。

单帧引擎模型：2073600像素、CRC及逐地址golden通过；新增DDR命令/转向压力后2079214周期，
名义125MHz为16.633712ms，距60Hz内部帧预算32.952us。
冷启动第一帧GammaON恒等曲线也通过。它们不证明连续系统或实板60新帧/秒。

先阅读 OPERATIONS.md、ROLLBACK.md、STA_SUMMARY.json 和 TEST_SCOPE.json。
源码/位流/同版报告绑定见 RELEASE_BINDING.json。
校验：python -B tools/verify_review_package.py
本包不操作开发板、串口或Flash。请由硬件持有人按已有受控流程验证并保留回退。
本包不是自包含重建工程，见 BUILD_BOUNDARY.md。

完整同版原始时序报告：timing/camera60-key1-m8-startup-final-sta-unclosed7ps.rtr
报告SHA256：3f06092752fc728b725e882ecd8c9e60a3a74c9c97e2e5ac486006c4c8e96bc0。汇总与唯一负路径见STA_SUMMARY.json。
