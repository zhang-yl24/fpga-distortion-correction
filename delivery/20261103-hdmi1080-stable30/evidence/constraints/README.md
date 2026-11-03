# 约束证据索引

- `stable-a-constraint-audit-final.json`：正式候选独立审计，33项通过。
- `diagnostic-inherited-groups-audit.json`：同ADF诊断尝试的预期失败记录；三个时钟组被ADF继承，未得到去组模型。
- `diagnostic-provenance.json`：诊断命令、输入ADF及约束哈希，输入ADF前后未变。
- `copied-evidence-manifest.json`：原始证据位置、包内路径、字节数和SHA256。

上述JSON保存历史绝对路径，复现时按 `../../docs/CONSTRAINT_AUDIT_REPRODUCTION.md` 指定本机实际构建路径。硬件稳定性和外部IO/CDC验收结果由上板记录补充。
