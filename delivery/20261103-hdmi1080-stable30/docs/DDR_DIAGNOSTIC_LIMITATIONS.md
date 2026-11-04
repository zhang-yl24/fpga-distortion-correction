# 同 ADF 诊断限制

正式候选的约束审计结果是 `evidence/constraints/stable-a-constraint-audit-final.json`：33项检查通过，0项待完成。该结果验证约束范围、四阶段原生PDS登记、优先布线实际执行及完整时钟端点归属。

另外进行过一次诊断尝试：在独立目录中只载入原诊断FDC、UART FDC和map PCF，然后对同一个最终routed ADF运行STA。输入ADF的SHA256为：

`0c6615b2dd9b83ee032e47c0bf990865d31ef9ba6baea68547099370e8981249`

本次运行成功，输入ADF哈希前后相同；输出clock interaction仍保留三个 Asynchronous Groups。PDS从ADF继承了时钟关系，省略附加FDC未将它们清除。因此 `evidence/constraints/diagnostic-inherited-groups-audit.json` 明确判定 `FAIL: diagnostic_really_removes_inherited_ip_clock_groups`，并保存了实际分组结果。`diagnostic-provenance.json` 记录原始命令、输入文件哈希和完成标记。

这次尝试确认了约束继承行为。它无法支持“同一布线去组后与正式模型对比成功”的结论，也不参与正式位流的导出门槛。

公开文档里的 `clear_constraint` 用于Map Design Workspace的PCF清理；`-disable` 说明单条命令无效化，未证明能够覆盖从ADF继承的条目。本包保留该限制，未修改最终ADF来制造去组结果。

硬件复位稳定性仍需冷启动、重复复位及持续DDR运行实测；受保护的 `ips2l_rst_sync_v1_3` 内部级数尚未独立验证。HDMI外部IO时序预算与CDC签核也须分别补齐。
