# 2026-10-31 录制相机帧的处理与输出回放

本轮按[用户最新方向](ACTIVE_DIRECTION_20261031.md)推进“摄像头画面→处理→HDMI输出”，暂停输入故障排查。摄像头仍接着，之前“没有接摄像头”为弹出问答误点。此次工作离板完成，没有下载新位流；最后确认的板上配置仍为合成八色彩条诊断。

## 完成结果

原生编译、展开、仿真均exit0。两幅不同的历史真实相机图像完整通过640×480回放，614,400个实际DE/RGB扫描像素逐点匹配独立Python整数参考。

| 历史场景 | 源CRC32 | 结果DDR / 读回 / 实际扫描CRC32 | 处理周期（125MHz数字模型） |
|---|---|---|---|
| 2026-10-09 偏左调整后棋盘 | 0002EC4C | 17D21875，三处一致 | 477,148 |
| 2026-10-09 偏右棋盘 | BD25B6A0 | EC527030，三处一致 | 477,153 |

实际执行既有Brown逆映射、双线性插值、Gamma帧引擎及结果写入器，经读仲裁、`ddr_video_reader`、真实 `video_async_fifo` 到 `ddr_video_output_1080_board`。DDR读写采用有背压的模型；原生扫描RGB逐点核对后，再导出像素由Python独立重读比较。

两帧共38,400个结果写beat及38,400个显示读取beat，0欠载、0 CRC错误。相同源bank/结果bank以新epoch串行复用，两次释放及最终排空通过，源数据保持不变。AW/W/AR实际背压分别2,408/7,439/3,075周期，FIFO峰值512。源码、相机数据及参考夹具前后哈希一致。

## 验证边界

- 数据来自10月9日修正D5后归档的 `gamma_capture_settled_d5` 实拍原图及其父目录来源记录，源预载模型DDR；没有实例化摄像头采集或HDMI RX。
- 使用合成非零Brown压力参数，不是当前镜头的标定。两帧Gamma判定均为GM0，本轮未覆盖提亮/压暗切换。
- 实际扫描模块适配640×480有效区、800×525总时序、25MHz像素时钟；不是1080p30/实物HDMI模式或实际帧率证据。上表处理周期不含完整扫描/帧调度，不能换算为端到端FPS。
- 串行源/结果租约由测试台管理，生产bank manager和并发调度未接入。CSV的source_epoch/result_epoch是测试台按帧ID标注的逻辑世代，bank_releases也是台架租约释放；生产扫描模块自身的request_epoch另有核对。相同bank复用和排空的结果只适用于此台架。
- 生产RTL、DDR IP和共享约束未改。既有1080八帧数字基线、旧640×480实板相机基线分别保留，不混用为本轮硬件验收。

## 独立HDMI TX配置

已有 `board/hdmi_tx_init.v` 在27MHz独立初始化MS7210，不依赖MS7200/HDMI IN；旧 `corrected_gamma_d5.v` 和 `raw_camera_capture_cam2_ref.v` 已使用它。新增线级回归实际执行控制器和 `reg16_i2c`，解析SCL/SDA，不替换事务或缩短计数。

原生三阶段均exit0；三个场景共54笔完整事务：scratch 5A写读与49项厂商设置共51笔成功事务；设备NACK场景1笔，error1且不ready；读回A5场景2笔，errorE且不ready。核对B2/B3、寄存器低字节先发、1ms/300ms间隔。完整错误重试等待和270,000周期启动延时保持，下一START出现在错误后27,270,070周期。未覆盖重试完成，也不证明发送器实物锁定或可见显示。

最终通过运行是 `distortion/build/hdmi-tx-only/wire-20261031-c`。a运行缺少展开timescale；b在成功路径及完整等待后触发测试台同事件监视竞态；c只补展开选项和测试台稳定采样边沿，生产RTL未改，a/b失败原件保留。

## 文件和复现

- [相机帧回放测试台](../distortion/tests/tb_recorded_camera_output.sv)、[运行器](../distortion/tools/run_recorded_camera_output_sim.py)。
- [回放持久证据清单](../distortion/results/recorded-camera-output-20261031/manifest.json)：19项文件，含原始报告、frames.csv、源图/参考/实际扫描PNG、压缩614,400像素、原生日志、41项源码/参考/数据夹具zip快照。
- [回放对照图](../distortion/results/recorded-camera-output-20261031/replay-preview.png)：历史相机原图与实际RTL扫描，明确标注数字回放/压力模型。
- [TX配置测试台](../distortion/tests/tb_hdmi_tx_init.sv)、[运行器](../distortion/tools/run_hdmi_tx_only_sim.py)、[TX持久证据清单](../distortion/results/hdmi-tx-only-20261031/manifest.json)。

在仓库根目录按需复现，使用未存在的独立workdir；无相关变更时不重复长仿真：

```powershell
.venv/Scripts/python.exe distortion/tools/run_recorded_camera_output_sim.py --workdir distortion/build/recorded-camera-output/NEW-EMPTY-NAME --maximum-seconds 900
.venv/Scripts/python.exe distortion/tools/run_hdmi_tx_only_sim.py --work-dir distortion/build/hdmi-tx-only/NEW-EMPTY-NAME --maximum-seconds 240
```

## 下一项

准备独立处理/输出板级候选，让扫描读取处理结果并独立启动MS7210。复用本轮已核对数据路径及27MHz TX初始化，定义模式、启动、复位/帧释放、源文件和本候选约束；核验新候选自身构建与物理结果后推进实板出图。`board1080_checked_top.v` 的现成RX→TX顺序及 `rx_done_ref/input_qualified` 门禁不能原样继承为这条路径的前置条件。输入调试继续暂停，DDR IP/共享约束保留原分工。
