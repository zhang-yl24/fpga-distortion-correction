# HDMI 1080p 稳定提帧候选

本版先争取 **1080p29.97/30 输入下接近每秒 30 个新校正帧**。已生成完整工程和诊断位流，尚待同学上板验收。固定纯校正配置为 `both / corrected`，参数身份 `8c73465e`。

## 本轮修复

1. **减少相位造成的整帧丢弃**：源帧缓存由两槽扩为三槽，使用 DDR 槽 0、1、4；结果仍使用槽 2、3。新增 4 MiB 外部 DDR 空间，并扩展 DMA 描述符排队。第三源槽可在校正或结果等待显示发布期间继续接收输入，并保留排队等待处理的源帧；源槽在引擎处理完成后释放。
2. **截短关键组合路径**：邻点地址和边界在缓存请求入队时预计算；DDR 写出增加 256 bit 数据寄存；DDR 读回的数据、有效、末拍和 ID 整组寄存，同时保持无主返回与重叠请求的故障检测。流水线延迟与控制信号一起对齐。
3. **恢复匹配版本的 DDR IP 约束**：补入厂商三条时钟关系和两条优先布线约束，核对 IP 版本、时钟负载及实际导入。保留用户域时序和 core↔PHY 数据检查。详细依据见 [DDR 审计](docs/DDR_RESET_CONSTRAINT_AUDIT.md)。

## 已完成的验证

| 项目 | 结果与范围 |
| --- | --- |
| 完整 1920×1080 引擎仿真 | 2,073,600 像素及有效掩码均匹配独立整数参考；CRC `4be2b2a6` |
| 125 MHz 引擎处理预算 | 2,831,328 周期，22.650624 ms；比原 baseline 25.748328 ms 减少约 12.03% |
| 两槽/三槽调度对照 | 30 个案例通过；本次不利相位下两槽 240 输入仅 180 新显示，三槽 240/240 |
| 真实小帧整机数字仿真 | 8/8 唯一输出，包含第三源槽反复写读、逐像素和 CRC 核验、故障与复位恢复 |
| 原生 PDS 流程 | Map、布局布线、独立双角 STA、位流导出均完成 |
| 内部原生时序 | Slow/Fast 的 setup、hold、recovery、removal、skew、MPW 共 12 类均零违规 |
| 最小 setup 裕量 | **+0.009 ns**，位于 core↔PHY 接口；该路径保留 0.4 ns 不确定度 |
| 资源 | FF 27,184/133,200；LUT 18,782.5/66,600；DRM 19.5/155；APM 69/240；IO 144/300 |

引擎仿真未覆盖真实板上的输入/显示 DDR 争用；调度实验中的处理时间采用受控模型。小帧整机验证真实模块连接，1080p 长时间运行由实板补充。三槽方案解决本次相位阻塞；处理时间超过一帧预算时仍会掉帧。

本版增加寄存器与控制逻辑来获得时序和调度余量，资源用量较旧组合版略增。维持输出像素一致，并未以降低画质换取吞吐。

## 上板与工程入口

下载完整交付 ZIP 后，先运行根目录 `verify_package.py`，阅读 `START_HERE.md` 和 [上板验收步骤](docs/BOARD_HANDOFF.md)。包内补齐原清单的 80 项依赖，支持在接收方电脑重新生成完整 PDS 工程。Git 中保留源码、测试与证据，ZIP 同时携带诊断位流与构建快照。

当前位流 SHA256：`f77c4991ef485466971fc9145d173769c1dcda3839665d72abfc4bc6288adeb4`。

位流保留 `DIAGNOSTIC_NOT_TIMING_SIGNOFF` 标签：原生内部时序已通过，HDMI 外部 IO 的 AC 约束、CDC/复位物理验收及板级长期稳定性仍需完成。加密 DDR 同步器内部级数尚无独立证明。约束修复与实物复位可靠性分别记录。

输入输出仍是 1080p29.97/30；参数沿用封存 Penn 配置，零旋转、Gamma OFF。1080p60 校正和新镜头标定不在本次通过项中。60 FPS 的每帧预算为 16.67 ms，当前引擎仿真预算仍需缩短约 26.4%，并联动输入、输出、DDR 仲裁和系统验证。

## 重现检查

Python 3.10+，从仓库或完整 ZIP 根目录运行：

```powershell
python -B delivery/20261103-hdmi1080-stable30/tools/verify_candidate.py
python -B -m unittest discover -s delivery/20261103-hdmi1080-stable30/tests -p test_*.py -v
```

完整引擎仿真需要 NumPy 和 XSim，输出目录必须尚不存在：

```powershell
python -B delivery/20261103-hdmi1080-stable30/tools/run_engine_benchmark.py --variant both --pressure --work D:/fpga-sim/new-engine --vivado-bin D:/Vicado/Vivado/2017.4/bin
```

`evidence/board/` 保留原构建回执与身份；`evidence/scheduler/` 保留冻结的调度、DMA 和整机验证；`evidence/engine/report.json` 绑定最终 RTL、参考结果和周期。历史回执内绝对路径用于追溯。新电脑重新执行 prepare，可生成当地路径的工程与输入身份。
