# 作品设计报告

当前正式报告为19页30 FPS版，采用团队成员本地摄像头下载验证结果，并保留两套15 FPS基线的完整设计与统计。沿用官方模板五部分，中文宋体、西文Times New Roman；19页均完成版式检查。

- [设计报告PDF](FPGA作品设计报告_20261104_提交整理版.pdf)：15.54 MB，适合阅读与提交。
- [可编辑Word](FPGA作品设计报告_20261104_提交整理版.docx)：与PDF同版。
- [正文Markdown](报告内容_20261104_提交整理版.md)、[更新说明](报告更新说明_20261104_提交整理版.md)与[当前结果参数](current_result.json)。

第5—6页为采图与标定流程；第11页为30 FPS方案的预取、缓存保护、DDR行突发写回及完整帧交接；第15页保留两套15 FPS基线的处理耗时范围，第16页给出30 FPS现场结果和a266对应时序；第17—18页为8张实物照片，第19页为总结和5项外部文献。

全文15张表、5张技术图及1个原生公式。原14表数值与照片字节保持；35.4515 ms仍只属于1080p15基线。a266的现场30 FPS与4条DDR PHY setup负裕量分别记录，不借用另一份KEY1构建的时序结果。

源码、位流与原始报告入口：

- [最新HDMI 1080p30技术说明](../../docs/HDMI1080_30FPS.md)。
- [OV5640 720p15基线](../../delivery/20261104-camera720p15/README.md)。
- [HDMI 1080p15基线](../../delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md)。
- [正式镜头参数](../parameters/LENS_CALIBRATION_PARAMETERS.json)与[照片来源](../photos/README.md)。

PDF使用Word原生页面生成300 dpi高清图像页，文本不可选择；编辑使用DOCX。`final-qa.json`记录文件SHA、保留项、逐页复核及PDF像素一致性。本轮生成与渲染脚本位于`tmp/report-teammate-refresh-20261104/`，未执行EDA或硬件操作。
