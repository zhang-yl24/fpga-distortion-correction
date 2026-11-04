# 作品设计报告

本目录的提交整理版已更新为24页实物图版，沿用官方模板，中文宋体、西文Times New Roman，黑字白底。第13、14页加入两套系统的8张实物照片，原照片占位全部移除；PDF用于阅读与提交，DOCX用于后续编辑。全部页面完成版式检查。

- 两套镜头正式参数、KB4-T2和输出投影探索、真实RTL仿真波形、HDMI同帧仿真延迟均保留。
- 第22页保留今早direct-fill同版板测、时序及资源；处理耗时采样约缩短20%，新校正帧率仍为15 FPS。
- `final-qa.json`记录本轮交付文件SHA256、照片来源、页数及逐页视觉复核。全部数值表、原生公式、原6张技术图和模板样式均保留。
- `报告内容_20261104_提交整理版.md`为作者正文源；例如 `![[architecture]]` 对应 `figures/architecture.png`。原六张技术图仍在figures；新增实物照片链接指向[`../photos/`](../photos/)，DOCX内嵌完整原始JPG。
- 更新说明中的`tmp/`为本机构建记录位置；正式文件、插图与最终QA均在本目录提供。数值实验与参数另见[`../evidence/`](../evidence/)和[`../parameters/`](../parameters/)。

历史版本的资源、时序、位流和帧率各自绑定，不混用为本次部署成绩。PC参考图及仿真波形不替代作品实物照片。

## 历史引用入口

PR #28回退后，报告参考[7][8]的队友记录仍保留在其原始提交；本次补实物照片不重新合入这些实验目录，历史参考与技术数值保留。

- 参考[7]：[stable30独立重建板测](https://github.com/zhang-yl24/fpga-distortion-correction/blob/23d3fd0d1dad662ecd263863e2f69d992454ab2e/delivery/20261103-hdmi1080-demo-source/progress/20261103-stable30-board/README.md)。
- 参考[8]：[Q512/O/P持续板测与源码交付](https://github.com/zhang-yl24/fpga-distortion-correction/blob/23d3fd0d1dad662ecd263863e2f69d992454ab2e/delivery/20261103-hdmi1080-demo-source/stable30-OP/README.md)。
