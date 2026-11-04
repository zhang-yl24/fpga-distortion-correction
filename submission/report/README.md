# 作品设计报告

正式入口已更新为17页文献与处理耗时修订版，沿用官方模板五部分，中文宋体、西文Times New Roman，黑字白底。PDF用于阅读与提交，DOCX用于编辑；17页均完成版式检查。

- 正式方案为OV5640 720p15与HDMI 1080p15直接填充实现；S3只在性能表中保留一行基线。
- 第5—6页说明完整帧采图程序：输入采样、帧冻结、UART封装、PC尺寸／CRC校验、原始图像与元数据存档以及标定流程。
- 全文14张表，七张正式参数与评价表保持原数值精度；包含两套同版新帧率、快慢角时序与资源结果。
- 五张技术图涵盖架构、帧同步、软件、采图流程和真实mapper波形。波形中的23拍是坐标映射单元延迟，系统吞吐采用板上帧计数。
- 第15—16页包含8张实物照片。DOCX嵌入原始JPG字节；便于仓库浏览的等比照片副本与来源记录见[照片目录](../photos/README.md)。

`报告内容_20261104_提交整理版.md`是正文源。图标记`![[architecture]]`、`![[frame]]`、`![[software]]`、`![[capture]]`和`![[mapper-waveform]]`对应`figures/`下同名PNG；`![[photos720]]`和`![[photos1080]]`分别展开对应方案的4张照片。`final-qa.json`记录最终文件SHA、模板保留检查、限字、照片身份与逐页视觉复核。

源码、位流和原生报告入口：

- [OV5640 720p15](../../delivery/20261104-camera720p15/README.md)。
- [HDMI 1080p15](../../delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md)。
- [正式镜头参数](../parameters/LENS_CALIBRATION_PARAMETERS.json)。

本轮修订和渲染脚本记录位置为`tmp/report-reference-refresh-20261104/`。本目录提供提交成品、正文、五张技术图和最终QA。

第14页新增720p仿真处理耗时14.09 ms与1080p板测采样35.45 ms的计时范围。参考文献已替换为5项真实外部来源。PDF为Word原生页面生成的300 dpi高清图像版，编辑使用DOCX；详见[修订说明](报告更新说明_20261104_提交整理版.md)。
