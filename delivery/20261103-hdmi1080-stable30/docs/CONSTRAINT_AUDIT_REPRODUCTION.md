# 约束审计复现

本包的正式历史证据来自 `D:/fpga-stable/build/stable-a`，source param ID为 `8c73465e`。JSON保留运行时的绝对路径、文件SHA、PDS登记及路由日志行号；其他电脑无需创建相同盘符路径。

在准备好完整native工程并运行 Map、Route、STA、Bitstream 四阶段之后，从本交付包目录执行：

```powershell
python .\tools\audit_stable_constraints.py --build "D:\your-prepared-build" --output "D:\your-prepared-build\constraint-audit.json" --require-final
```

`--build` 指向包含 `preparation.json`、`native/` 和 `stages/` 的已构建目录；`--output` 指向新的审计JSON。请替换这两个绝对路径。脚本只读取工程与报告，写入指定JSON，不调用PDS、不修改RTL或构建脚本。缺少最终阶段证据时，`--require-final` 会失败；调试过程中可以省略该标志查看待完成项。

检查范围包括：恰好三条匹配版本厂商时钟组、无新增false_path、20个用户有向时钟域组合的8 ns/0 ns约束、core与divided PHY间的真实时序约束、两条prior_net实际执行、四阶段PDS约束类型及SHA、完整时钟树的所有权。相关官方依据见 `DDR_RESET_CONSTRAINT_AUDIT.md`，最终结果见 `STABLE_A_FINAL_CONSTRAINT_AUDIT.md`。

`--diagnostic-report-db` 仅用于额外的同ADF对照实验。传入本次已归档的诊断尝试会按设计报告失败，因为工具仍继承三个时钟组；具体说明见 `DDR_DIAGNOSTIC_LIMITATIONS.md`。常规候选约束审计无需该参数。

当前候选的12项原生STA汇总均通过；最小setup余量为 +0.009 ns，位于core至PHY数据路径。板上持续帧率、冷启动和复位恢复、HDMI外部IO时序及CDC验收应单独记录。
