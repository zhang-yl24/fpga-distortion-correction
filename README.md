# FPGA 实时图像畸变矫正

盘古676 / PG2L100H-6IFBG676项目。三人轮流推进的私有协作仓库。

**先阅读 [交接说明](handoff/交接说明.md) 和 [当前交接点](handoff/CURRENT.md)。**

- [已完成工作与验证范围](distortion/output/project/成果记录.md)
- [实验操作表](distortion/output/project/实验操作表.md)
- [推进计划](distortion/output/project/推进计划.md)
- [原始工程说明和历史记录](distortion/README.md)
- [首次完整交接附件](https://github.com/zhang-yl24/fpga-distortion-correction/releases/tag/handoff-20261010)

源码、必要DDR/PLL IP、真实采集数据、当前实验结果和文档在仓库内。历史构建及封存证据在同版本Release附件中；已生成稳定位流可从`starter-artifacts.zip`导入，无需先重新编译。详见交接说明。

本次整理执行文件依赖、SHA256、附件内容和远端上传核对；未在原电脑重新下载、运行参考测试、重新构建或访问开发板。参考测试交给GitHub Actions；云端不具备PDS许可证和板卡，不能代替整板构建或实物验收。

厂商IP及引用代码保留原有归属和许可，未为整个工程另设开源许可。PDS软件和本机许可证须在各自电脑配置，不随仓库分发。
