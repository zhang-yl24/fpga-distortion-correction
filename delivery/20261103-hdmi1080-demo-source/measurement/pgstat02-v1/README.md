# PGSTAT02 v1：固定profile测量工具源码交付

作者原始普通ZIP已只读核实：198338B，SHA256 **`789ca1305038901b1825a57e4fba7bb2dc2f1615f5a8143539af84a0557145ee`**。来源为作者明确提供的本地原件；不是Library临时下载残片，也没有补写Library元数据。此前Library辅助程序在Windows元数据阶段失败的记录保持原样。

这里按原字节保留v1自有`host/`、`tests/`、合成/规范请求fixture、6项语义审查RTL和必要说明/证明。`AUTHOR_SOURCE_PROVENANCE.json`逐项绑定原ZIP成员与交付路径；原README和完整清单分别保留为`AUTHOR_README.md`、`AUTHOR_PACKAGE_SHA256.json`。嵌入v0 ZIP/旧v0结果和不必要打包中间文件不随本交付发布，v0不得作正式验收工具。

## 立即运行离线回归

仅需Python 3.10+标准库，在此目录运行：

```powershell
python -X utf8 -B run_delivery_checks.py
```

若运行环境的默认Temp不可写，可显式指定已有可写目录，例如 `--scratch-parent C:\Users\22955\AppData\Local\Temp`。包装脚本校验解析后的临时子目录范围；原作者host、测试和oracle保持不变。本次交付端在该显式Temp中重跑34项全部通过。

该入口先校验精确作者文件及6项RTL语义绑定，再复制到系统临时目录运行原作者34项内存测试。原始host、bench和oracle未改；合成fixture重写仅发生在临时目录。不会导入串口库、打开COM、发送实际UART、烧录、执行EDA或改动原始ZIP/生产工程。

作者34项回归及主线程独立25组合法/反例已通过；本交付再次运行作者34项。独立25组计数来自主线程复核，不与重复运行次数相加。LIVE类别测试使用注入的内存传输，不是现场采集证据。作者原`run_offline_checks.py`依赖完整历史v0 ZIP保全，未作为此源码子集的入口；请使用上述交付入口。

## 绑定与能力边界

工具仅适配当前固定纯校正PGSTAT02 profile：1920×1080、固定mode1、Gamma OFF、nominal125MHz、无PGFRAME，诊断bit SHA256 **`57044fe803d9880f016b53c91234def946bb13da6cc1d357cd15689a5212a374`**。它不是D256或60Hz新构建；该bit本身仍有setup/复位/IO问题且未实板验收。修改manifest中的SHA字符串不能证明现场正在运行该固件。

v1补充native最少处理周期、`(accepted-completed) mod2^32 = processing`原子计数关系、窗口完成数上界和精确输入文件字节身份检查。支持合法uint32进位；不能证明cycle residue未wrap时保留null，不写成绝对延迟。canonical三条请求与现有RX限制保持绑定，不声明任意混合命令流正确。

离线报告入口为`host/measurement_report.py`；`host/collect_measurement.py`包含后续显式live采集入口，本次没有执行。实际端口、加载回执、连续reset epoch、输入来源和包边界必须由主工程现场确认。具体参数及证明见[作者说明](AUTHOR_README.md)、`reference/MEASUREMENT_RUN.md`与`work/V1_SEMANTICS_REVIEW.json`。

**这些检查不证明现场固件身份、真实125MHz、全帧延迟分布、光学唯一FPS或外部E2E。** 两个端点最多提供稀疏末帧处理样本；输入接受到完成不含曝光、HDMI接收前段和显示扫描。合成报告数值不是硬件成绩，也不能称60个新校正帧/秒已达到。
