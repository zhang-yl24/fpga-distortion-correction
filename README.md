# FPGA 实时图像畸变矫正

盘古676 / PG2L100H-6IFBG676项目。三人轮流推进的私有协作仓库。

**先阅读 [交接说明](handoff/交接说明.md) 和 [当前交接点](handoff/CURRENT.md)。**

## 当前方案与进度（2026-10-30）

当前主链目标是 **1920×1080、30 fps 实时畸变矫正**：HDMI 输入 → DDR 帧缓存 → 畸变坐标计算、四邻点采样与双线性插值 → 输出帧缓存 → HDMI 显示。OV5640 的历史采集工程另行保留，尚未直接接入这条 HDMI 主链。

| 范围 | 已验证结果 | 尚待完成 |
|---|---|---|
| 1080p30 主链 | 已记录八帧、16,588,800 像素/CRC及稳态 30 fps 的数字仿真 | 当前完整主链的实板画面、实际新增帧率、标定与长稳 |
| HDMI 独立诊断 | 本机 SRAM 下载、DONE=1；复位释放后等待 100 ms 的候选恢复 I²C 应答 | RX/TX 初始化完成、真实输入和显示输出 |
| 串口观测 | 延迟候选两次接收共 50 包，CRC 全部正确、配置错误为 0；追加 20 秒成功事务增加 131,049 次 | 重复冷启动和更长时间稳定性 |
| 诊断候选实现 | 延迟配置版的双角十类原生时序检查通过，42 个引脚及方向匹配 | 外部接口时序；该结果不能代替主工程最终 STA |

最后一次确认下载的是独立 `hdmi_uart_delayed_diag`，仅含 HDMI 配置、UART 和 FPGA 测试彩条，不含 DDR 或畸变矫正主链，未写 Flash。RX 仍在轮询输入状态，RX/TX 初始化尚未完成；这次恢复应答支持增加复位后等待，尚未证明重复冷启动可靠性。带完整输入观察器的另一诊断候选时序未通过，未下载。

- [实板诊断说明与复现命令](distortion/docs/HDMI_UART_BRINGUP_20261030.md)
- [结果汇总与完整证据包哈希](distortion/results/hdmi-uart-20261030.json)、[随仓库保存的原始串口及回执](distortion/results/hdmi-uart-20261030/)
- [主工程复位等待补丁说明](handoff/patches/hdmi-post-reset-wait.md)：补丁尚未应用，集成后须重新构建及检查时序。

## 下一步接线与验证

准备两根 HDMI 公对公线：**电脑 HDMI 输出 → 开发板 HDMI IN；开发板 HDMI OUT → 显示器 HDMI 输入**。显示器选择对应输入；电脑使用扩展显示，将 FPGA 对应显示输出设置为 1920×1080、30 Hz，如系统尚未识别该模式则先检查配置与 EDID。

保持下载器和板载 UART 连接。本机 UART 为 CP210x **COM7，115200/8N1**；端口号在其他电脑上须重新识别。PDS 下载使用 USB Cable II，UART 用于读取 PGHDMI01 状态，两者用途不同。接线后先确认 I²C 无错误、RX/TX 初始化完成，再检查测试彩条。当前诊断版预期显示 FPGA 彩条；完整矫正画面需后续主链集成与验证。

## 历史进展

以下记录对应各日期、各候选及各测试环境；其中“未访问开发板”等描述仅指当时那次工作。历史相机图像和帧率不作为当前 1080p HDMI 主链的实板验收。

2026-10-29：已从修复后的最终 ADF 生成离线 `.sbit`，并在生成前执行原生时序/例外审计；实际 rowpipe 板级控制回归也已通过。未访问开发板，实物 HDMI/DDR/相机验收仍待完成。见[离线进展与下一步](handoff/BOARD1080_OFFLINE_NEXT_20261029.md)。

2026-10-29：DDR 定向时序修复候选已在同一已布线副本中通过 PDS 双角十类原生报告审计。局部 `_N173` 数据支路绕行消除 slow/fast hold 失败；精确 IP 复位例外覆盖244项内部检查及1项入口RDC，setup/hold false-path保持为空。结果仍是离板候选，外部 IO、CDC、DDR训练和实板验收未完成。详见 [DDR 时序修复](handoff/BOARD1080_DDR_TIMING_FIX_20261029.md)。

2026-10-28（修复前历史基线）：rowpipe已接入1080P整链，新源八帧16588800像素/CRC及稳态30.000fps数字回归通过；逐帧处理周期未下降，未声称提速或实板fps。PDS2023.2完整流程当时有每角1项PHY hold及slow245/fast234项recovery。修复后离板候选见[DDR时序修复](handoff/BOARD1080_DDR_TIMING_FIX_20261029.md)。

2026-10-28：新源1080八帧离线数字链路通过；此行记录修复前复位/RCF物理诊断，修复后状态见当前交接点。

2026-10-25：新模组CAM2已取得真实640×480原图与内部彩条，七项受限控制实板测试通过；另一眼读到OV5640 ID，但启用数据输出后的SCCB读取失败，尚未采图。完整720p帧的下游数字仿真通过，传感器720p模式仍待解决时钟资料矛盾。实际视场、标定、画质、双目同步和新镜头性能分别验收；按任务推进，11月4日前完成提交。

- [持续开发成果与实际图像](distortion/output/project/持续开发成果-20261025.md)
- [开灯后房间原图与补采结果](distortion/output/project/开灯后原始采集-20261025.md)
- [CAM1单变量诊断与最新计划调整](distortion/output/project/CAM1单变量诊断与计划更新-20261025.md)
- [重新上电与复位隔离的最新结果](distortion/output/project/重新上电与复位隔离复查-20261025.md)
- [FPC插紧后的复测与诊断推进](distortion/output/project/FPC插紧后复测与诊断推进-20261025.md)
- [10月26日新事务诊断实板结果](distortion/output/project/CAM1事务诊断实板结果-20261026.md)

- [本轮离线成果与接板入口](distortion/output/project/新镜头离线进展-20261025.md)

- [新镜头任务计划](distortion/output/project/推进计划.md)
- [离线工具与运行入口](distortion/output/project/新镜头离线工具说明.md)
- [接板验收单](distortion/output/project/明日接板验收单-20261025.md)
- [冲奖证据矩阵](distortion/output/project/冲奖证据矩阵-20261024.csv)

- [已完成工作与验证范围](distortion/output/project/成果记录.md)
- [实验操作表](distortion/output/project/实验操作表.md)
- [推进计划](distortion/output/project/推进计划.md)
- [原始工程说明和历史记录](distortion/README.md)
- [首次完整交接附件](https://github.com/zhang-yl24/fpga-distortion-correction/releases/tag/handoff-20261010)

源码、必要DDR/PLL IP、真实采集数据、当前实验结果和文档在仓库内。历史构建及封存证据在同版本Release附件中；已生成稳定位流可从`starter-artifacts.zip`导入，无需先重新编译。详见交接说明。

首次交接整理执行文件依赖、SHA256、附件内容和远端上传核对，当时未重新访问开发板；10月25日后的本地构建和实板事件见当前交接点。GitHub Actions不具备PDS许可证和板卡，不能代替整板构建或实物验收。

厂商IP及引用代码保留原有归属和许可，未为整个工程另设开源许可。PDS软件和本机许可证须在各自电脑配置，不随仓库分发。
