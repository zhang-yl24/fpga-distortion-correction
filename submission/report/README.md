# 作品设计报告

本目录的提交整理版共22页，沿用官方模板，中文宋体、西文Times New Roman，黑字白底。PDF为阅读与提交用文件，DOCX用于补照片和后续编辑。当前正文完成，**第12页三处实物照片待补**；补齐后需重新导出并检查PDF。

- 两套镜头正式参数、KB4-T2和输出投影探索、真实RTL仿真波形、HDMI同帧仿真延迟均保留。
- 第20页新增今早direct-fill同版板测、时序及资源；处理耗时采样约缩短20%，新校正帧率仍为15 FPS。
- `final-qa.json`记录交付文件SHA256、模板身份、页数及视觉复核。此处记录针对补图前版本。
- `报告内容_20261104_提交整理版.md`为作者正文源，保留原始插图占位标记；例如 `![[architecture]]` 对应 `figures/architecture.png`。六张插图已随本目录提供。
- 更新说明中的`tmp/`为本机构建记录位置；正式文件、插图与最终QA均在本目录提供。数值实验与参数另见[`../evidence/`](../evidence/)和[`../parameters/`](../parameters/)。

历史版本的资源、时序、位流和帧率各自绑定，不混用为本次部署成绩。PC参考图及仿真波形不替代作品实物照片。

## 历史引用入口

PR #28回退后，报告参考[7][8]的队友记录仍保留在其原始提交；本次不重新合入这些实验目录，报告成品字节不变。

- 参考[7]：[stable30独立重建板测](https://github.com/zhang-yl24/fpga-distortion-correction/blob/23d3fd0d1dad662ecd263863e2f69d992454ab2e/delivery/20261103-hdmi1080-demo-source/progress/20261103-stable30-board/README.md)。
- 参考[8]：[Q512/O/P持续板测与源码交付](https://github.com/zhang-yl24/fpga-distortion-correction/blob/23d3fd0d1dad662ecd263863e2f69d992454ab2e/delivery/20261103-hdmi1080-demo-source/stable30-OP/README.md)。
