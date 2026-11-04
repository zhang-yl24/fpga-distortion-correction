# 作品设计报告

当前正式报告为19页1080p方案对照版，采用本地摄像头验证成功的1080p30结果，保留1080p15及720p15的设计、统计和实物演示。全文沿用官方模板，已完成逐页版式检查。

- [设计报告PDF](FPGA作品设计报告_20261104_提交整理版.pdf)：15.65 MB，用于阅读与提交。
- [可编辑Word](FPGA作品设计报告_20261104_提交整理版.docx)：与PDF同版。
- [正文Markdown](报告内容_20261104_提交整理版.md)、[更新说明](报告更新说明_20261104_提交整理版.md)、[结果配置](current_result.json)和[源码对照依据](源码对照依据_20261104.json)。

技术部分介绍采图、标定、鱼眼映射与完整帧处理，补充30 FPS实现的源帧队列、前瞻预取、数据保护和DDR行突发写回。表15将1080p15与1080p30的源码结构和性能并列，说明同分辨率新校正帧率从15 FPS提升至30 FPS的工程变化。

两套15 FPS基线保留按键原图／校正演示、对应时序与资源、完整帧统计以及处理耗时；正式标定参数、5项外部文献和8张原始照片继续保留。

源码、位流和资料入口：

- [HDMI 1080p30](../../docs/HDMI1080_30FPS.md)。
- [HDMI 1080p15对照](../../delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md)。
- [OV5640 720p15](../../delivery/20261104-camera720p15/README.md)。
- [镜头参数](../parameters/LENS_CALIBRATION_PARAMETERS.json)与[照片来源](../photos/README.md)。

PDF为300 dpi高清图像页，文字不可选择；编辑使用Word。`final-qa.json`记录文件SHA、内容保留、逐页复核与PDF页图一致性。本轮生成记录位于`tmp/report-fixedcorr-refresh-20261104/`。
