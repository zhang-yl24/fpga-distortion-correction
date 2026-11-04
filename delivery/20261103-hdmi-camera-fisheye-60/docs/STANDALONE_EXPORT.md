# 独立工程导出

`tools/prepare_candidate.py` 使用完整仓库中的 C 版封存清单、原始源码/IP 及候选覆盖文件建立编译闭包。交付一个脱离仓库即可重建的工程时，先冻结最终 prepare 结果，再导出：

```powershell
python tools/export_standalone.py --prepared D:/f60-final-prepared --output D:/f60-standalone
python D:/f60-standalone/rebuild.py --verify-only
python D:/f60-standalone/rebuild.py --output D:/f60-rebuild
```

导出包含 `compiled/` 的全部输入、原 `candidate-plan.json`、原 `build.tcl`、独立 `rebuild.py`、说明及 bundle SHA 清单。PDS 工具和构建缓存不进入导出包。导出与重定位均使用 Python 3.9+ 标准库，不调用 EDA 或硬件。

`rebuild.py` 可在 bundle 移动后运行，先检查全部源文件、Tcl、脚本与清单，确认 Tcl、Verilog include 和 DDR IDF 依赖闭合，再将绝对编译根重定位到新的短目录。重建回执保存原始身份、标定/构建 ID、新文件 SHA 和实际改动的 include 清单。输出目录已存在时会拒绝操作。

`evidence/standalone-export/` 记录 114 输入的独立导出验证：搬移 bundle 后验证成功，在含空格的路径重建成功，逆向替换编译根后所有文件字节与原快照一致；破坏 SHA 的输入会被拒绝，已有目录的文件保持不变。该验证快照早于最后的 lane FIFO 修改，证明导出工具行为；最终发布应对最终 prepare 目录重新导出并验证。
