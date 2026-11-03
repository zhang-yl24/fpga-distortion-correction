# HDMI 60 Hz、三源槽与 DDR 返回寄存

这组覆盖文件基于已上板 C 版，维持 RGB565 量化、鱼眼参数 `ed59f83e3cfbc77b`、原图/校正 KEY1 切换和共同复位。默认构建标识为 `0x11036003`（上 lane 640 行、INDEX10 行填充；下 lane 440 行、INDEX9 线性索引）。C 版目录和 `distortion` 基线文件保持原样。

## 行为变化

- 输出像素时钟直接使用 `pixclk_in`，沿用已上板直通顶层的时钟连接方式。输入约 148.5 MHz、扫描 2200 × 1125 时得到 60 Hz。去除原 74.25 MHz 视频 PLL 和对应的锁定条件，保留配置 PLL、DDR 就绪、输入时钟活性 watchdog 和故障锁存。
- 三个逻辑源槽 0/1/2 映射到 DDR 物理槽 0/1/4；结果槽仍为 2/3。每槽步长 `0x100000` 个 4 字节地址单位，即 4 MiB。第三源槽地址为 `0x400000` 地址单位，即 16 MiB；全部五槽占用 20 MiB 地址范围。
- DMA 使用两个完成描述符位置。已有 head 在接收方停顿时保持稳定，下一帧可在第三槽捕获并成为 tail；完成数据写入、CRC 检查和 DDR 写排空后才发布。消费 head 时原子提升 tail，捕获仍须预留完成描述符容量。
- DDR 读返回的 256 位数据、valid、last、4 位 ID 同拍寄存一级。原始接口先检查事务归属，避免新增延迟把无主返回归给后来的地址。无主返回为锁存错误 `0x40`，重叠请求为 `0x41`；原仲裁器继续检查 ID、末拍和超时。错误进入系统停止接收路径，共同复位释放整个事务周期。
- 输出消费者采用四个显式 256 位寄存字，活动字每个像素移位 16 位。CRC 从已寄存的低 16 位像素更新，去除异步队列读/16:1 像素选择路径。末像素按原光栅位置输出，同时寄存最终计数检查结果；下一拍验证计数与整帧 CRC，再发布完成记录。同步 abort、无主返回和 disable 在末像素拍及验证拍均保持即时优先故障否决。
- 四个私有数据寄存字的使能仅依赖本地 reset/failed 和入队/移位操作，去除组合 fault_now 对 1024 位数据的宽扇出。故障同拍允许内部字更新，主控制立即清除队列所有权并否决 RGB、pixel_valid 和新成功记录；failed 随后隔离这些私有数据，直到共同复位及重新填充。已发布且未 ACK 的 done 元数据独立存储，继续保持不被覆盖。
- 每个 16 像素字的结束位置提前一拍译码并寄存为单比特。合法配置要求图像宽度为 16 的倍数且完整位于扫描范围，因此行内偏移 14 的下一拍始终为同一图像行的偏移 15。pop 仍在当前拍检查 frame_active、queued 和 failed；复位、行消隐及新 grant 均保留原来的数据移动时刻。真实 1080 和两种小图光栅逐拍断言新位置位等于原组合位置条件。
- 图像矩形位置也提前一拍译码：位置寄存器使用与 x/y 完全相同的下一坐标及行、帧回绕条件。复位时图像位置为 0，合法配置的 `(0,0)` 位于图像外。当前所有权、队列深度及当拍故障继续直接控制消费和发布；CRC、像素位置、HS/VS/DE 与完成时刻保持原样。
- 完成记录的 epoch、ID、bank、CRC 和像素计数共 129 位在租约活动或完成确认期间独立预取。只有完成 toggle 发布记录，good 与 toggle 保留当拍完整故障否决。未 ACK 的记录禁止预取覆盖，包括 ACK 同步到达与故障重合的边沿；末像素后确认拍同时采最终 CRC/计数和发布，周期不增加。
- 请求 epoch 在无旧请求、无活动租约和无排队数据的扫描边界独立准备，request toggle 仍由当拍完整故障检查决定是否发布。故障同拍准备的 epoch 不会成为新请求；旧请求尚未确认时，epoch 与 toggle 都保持稳定。
- UART 协议仍分别统计输入、捕获、处理、有效显示新帧、扫描刷新、重复帧和空白帧。主机解析器拒绝旧 BuildID 与错误的标定 ID，刷新率与有效新帧率分别报告。

两个主机工具均支持显式 `--build-id`。参数只接受 24 种明确候选组合：默认 rowpad640 为 `11036003`、历史 rowpad544 为 `11036002`、uniform7/8/9/10 对应 `11036007/08/09/0a`；32×8 tile 增加 `0x100`，DDR CA fanout16 实验增加 `0x1000`。选定后每个 UART 包必须精确匹配该 ID 和固定 profile，混合版本会被拒绝。physical-d 使用 `--build-id 11037003`；历史 physical-c 使用 `--build-id 11037002`。uniform 仍采用 544/536 行分工。历史 physical-b 的 `11036001` 仅保留诊断证据。

引擎外部 `frame_valid/frame_ready/done` 接口保持原样。双 lane 引擎输出须由 writer 恢复为 raster 布局；`RESULT_TILED` 入口保留，当前有效值为 0。

## 完成描述符分级验收

系统分别保持显示租约、reader 完成记录和像素完成记录。完成事件先保存记录，下一拍对 ID、epoch、CRC、计数各做独立 16 位分段比较，再下一拍形成 validated 状态。像素完成 ACK 仅在本地保存及比较之后发出；ACK 后外部总线可复用，本地快照继续保持到银行实际释放。重复完成事件和无主完成事件都不能覆盖已有快照。

两份完成记录验收通过后，还需 reader 空闲、FIFO 排空、grant ACK 到达及当前无故障，才准备释放。`bank_release_accept` 在银行实际消费边沿再次核对当前故障、lease、bank、grant 状态和新的异常事件。scan_good、新帧与重复帧统计仅由这个相同事件增加；提前准备的 release 脉冲不会计数。当前 fault、释放拍晚到 fault、FIFO 重新出现数据或 bank 状态变化都会拒绝释放。

22 组定向测试使用真实 controller/bank，驱动 reader/scan 的 held bundle 边界，覆盖所有字段错误、重复/无主事件、reset、ACK 背压、总线复用和释放拍故障。真实双 lane 系统竞争测试另验证实际 capture、DDR、mapper/cache/writer、扫描及两次共同复位 epoch。

## 构建接入

用本包 `rtl` 中以下同名模块替换基线对应文件，避免同时编译两个同名定义：

| 文件 | 模块/变化 |
| --- | --- |
| `hdmi_camera_fisheye_top.v` | 输出源时钟、BuildID、RESULT_TILED 参数 |
| `hdmi_camera_fisheye_system_c.v` | 模块名 `hdmi_camera_fisheye_system`，返回寄存和三槽接口 |
| `hdmi_camera_fisheye_bank.v` | 三源槽逻辑和 0/1/4 地址映射 |
| `hdmi_camera_fisheye_input_link.v` | 三槽、完整提交元数据与故障连接 |
| `hdmi1080_input_dma.v` | 三槽和两个完成描述符 |
| `hdmi1080_capture_cdc.v` | 2 位源槽元数据跨域 |
| `ddr_read_return_register.v` | 新增编译源，完整读返回束寄存 |
| `ddr_video_output_1080_board.v` | 替换 experimental 同名模块，寄存移位取像素、下一拍确认整帧 CRC |

系统调试端口 `source_commit_bank`、`released_bank` 为 2 位，`capture_reserved` 为 3 位。结果槽索引仍为 1 位，发布物理结果槽为 2 位。上层测试台与调试绑定须使用相应宽度。

顶层构建须保留 C 版已确认的 `INPUT_TIMING_CONFIGURED=1`、VS/DE 极性设置。默认值 0 继续阻止未经配置的启动。`cfg_corrected` 按整帧握手生效。

按顺序载入：

1. `constraints/hdmi-camera-fisheye-60-internal.fdc`
2. `constraints/ddr-ip-clock-relations.fdc`
3. `constraints/board1080-ddr-ioclk-priority.rcf`

主 FDC 将输出时钟定义为输入 PCLK 的 1:1 转发，输入时钟使用 6.6667 ns 的内部约束。DDR 的生成时钟、位置、两条 multicycle 和四条 uncertainty 沿用 C 版。附加 FDC 精确补入厂商的三个 IP 内部时钟组，具体范围见 `DDR_IP_CONSTRAINT_AUDIT.md`。

## 已运行验证

全部结果位于 `evidence/video-control/`，JSON 记录测试源 SHA-256；完整日志保留在对应子目录。最终输出覆盖结果为 `output60-done-private/results.json`，完成描述符和系统错误接入为 `system-completion/results.json`。早期输出及系统结果目录保留各轮基准证据。

| 验证 | 结果与范围 |
| --- | --- |
| DMA + input link | 真实 capture/DMA/write arbiter；三个源槽、head 停顿/tail 提升、帧损坏与溢出后排空、非法释放、复位恢复通过 |
| 调度相位 | 两槽 C 与三槽对照，共 30 组；三种处理延迟 × 五种相位中三槽均显示 240/240 帧且无缺槽；两槽在六组显示 180/240 |
| 读返回 legacy/integration/guard | 原仲裁器、1/2/8/16 拍、同拍地址与首返回、连续/间歇返回、原始无主/重叠、ID/末拍/超时、共同复位通过 |
| 系统接入读返回 | 实际 system/bank/input/reader/arbiter/FIFO，空闲 engine stub；无主返回锁存 0x40、停止接收、无客户端 valid 泄漏、共同复位恢复通过 |
| 完整 1080p60 扫描 | 两帧独立像素及 CRC oracle；每帧 2073600 像素、129600 beat，首像素间隔 2475000 时钟周期/16.666666667 ms；逐拍断言预译码位置与原组合条件一致 |
| 148.5 MHz 输出故障 | 缩小帧、真实同步读异步 FIFO；两种光栅各二十组，共 40 组；包含同拍 pop/真实 owned return/abort、末像素 pop/无主 return、完成确认拍 abort、扫描边界 abort/disable/无主返回/旧请求未 ACK、ACK 同步到达与原始故障同拍。逐次发布核对边沿前的租约/CRC/计数快照，断言未 ACK 的 held bundle 不变、私有预取不发布、所有权清空和持续排空 |
| 位置预译码边界 | 六种自然扫描光栅：WX=0、WY=0、中心裁切、紧贴行帧末端、HT=4096、VT=4096；逐拍对照原矩形与 word-end 条件，包含扫描中复位、故障后继续扫描和每配置两次帧回绕 |
| 系统完成验收 | 22 组真实 controller/bank 边界注入，五次实际银行释放；每次统计增加均与同边沿 bank 接收一致，错误记录及晚到故障零释放/零统计 |
| UART 主机 | 八项 unittest：24 种构建候选的精确身份、非法/旧 ID 拒绝、混合身份拒绝、固定标定身份、帧率区分、碎片损坏恢复、计数回绕、复位 epoch、切换/故障拒绝 |

调度使用可控引擎延迟。完整扫描测试使用一拍 FIFO 返回模型，不包含 DDR 带宽竞争。以上证据支持控制逻辑和 60 Hz 扫描行为；全帧校正吞吐、原生布局布线时序、外部 IO 和实板持续运行由最终集成验收补充。

## 原生时序诊断与改动依据

`physical-a-diagnostic/` 保留首轮 PDS 诊断。该快照尚未包含输出流水、新 engine 注册启动及三条厂商时钟组，slow 输出同域 WNS 为 -3.517 ns，core 同域 -2.962 ns，core→divided PHY0 为 -0.810 ns。输出实际路径为队列读/像素选择→CRC→比较→高扇出故障控制；本次输出覆盖针对该链修改。该轮资源为 DRM36K 等价 61/155、APM 96/240。后续候选必须重新布局布线和验收，当前逻辑仿真不替代物理时序结论。

`physical-b-diagnostic/` 保留同步 metadata / uniform9 候选摘要。该轮 slow 输出同域 WNS 为 -1.692 ns，core 同域 -3.264 ns，core→divided PHY0 为 -0.788 ns；同域 hold 零失败。输出最差路径为 pixel_count→final_counts_ok→fault_now→pixel_count CE，随后用独立计数检查寄存器切断。该轮尚未包含此修复。DDR 约束实际导入与时钟归属审计通过；时序尚未收敛。证据只收录摘要、每域前 12 条路径及原始文件 SHA-256，完整报告保留在本地工作目录。

`physical-c-diagnostic/` 绑定 rowpad544 + fanout16：slow core→PHY0 为 +0.008 ns、PHY1 为 +0.011 ns，两组零 setup 失败；core 同域 -3.675 ns、输出同域 -3.031 ns，仍有失败路径。该快照尚未包含双项 FIFO 反压隔离与最终计数采样寄存。DRM36K 等价为 147.5/155。全部角摘要保留独立用户时钟域的违规结果，外部 IO 和 CDC/复位验收继续待完成。

`physical-d-diagnostic/` 绑定 rowpad640 + fanout16，并包含反压 FIFO 与最终计数采样：slow core 同域 -3.954 ns，输出同域 -2.762 ns。输出最差路径为 display_fifo 的读复位同步→ready→fault_now→word1 宽数据使能；随后移除了该组合故障门控。该轮 DRM36K 等价 147.5/155，时序结论继续标为诊断失败；更新的输出和 writer 必须重新布局布线确认。

交付包 `evidence/physical-g/timing.json` 的输出同域最差 setup 为 -0.820 ns，实际链为 y→图像位置→consume/pop→word1 宽使能，数据延迟 6.975 ns，其中布线 5.577 ns。随后将 pop 的位置条件提前一拍寄存，保持所有非位置条件和故障否决原样；当前通过两帧和 38 组功能回归，物理改善需由后续布局布线验证。G 的其余输出路径留待后续实测决定。

`sampler-release-equivalence/` 另保留三段复位释放采样器的备用实验：37,940 次稳定态比较和 13,540 个 PCLK 沿通过，包含停止 PCLK 时异步复位、同沿断言/释放及首样本边沿。该实验仅修改临时副本，live sampler 保持冻结。

H 输出最差路径为 y→picture→consume→word0 CE，setup -1.872 ns；FIFO ready 经故障条件到 129 位完成字段使能为 -1.228 ns。后续分别采用图像位置预译码和未发布完成字段预取，保持控制发布时刻及故障优先级。原生时序改善由下一完整候选验证。

`writer-beat-maxfan32/` 保留普通 beat 寄存器扇出属性的独立 PDS 编译、综合、器件映射证据。四位 beat 从 4 个寄存器复制为 116 个，综合每个输出最大扇出 32，map 的已报告 beat 网最大扇出从 2052 降至 32；单 writer probe 增加 112 个 FF，周期不变。每位副本的 D/CE/CLK/R 与初始化参数一致，RTL 功能 token 与 H 相同。该属性已加入 writer；此证据验证实际复制，未包含独立 probe 布局布线结论。

`tools/summarize_native_timing.py --project <PDS目录> --output <摘要.json>` 可重新生成 JSON 与 Markdown 表。脚本读取 slow/fast 的 setup、hold、recovery、removal、mpw 和 skew 共十二类摘要与每域最差十二条已报告路径，并封存报告 SHA-256、源身份及外部 IO/CDC 状态；只在每域最差 setup 路径附详细到达链。

## 复跑

在本包根目录运行，`--work` 应指定新的目录，避免覆盖先前证据：

```powershell
python -B tools/run_video_control_checks.py --work D:/f60-work/recheck-control --vivado-bin D:/Vicado/Vivado/2017.4/bin
python -B tools/run_video_scheduler_checks.py --work D:/f60-work/recheck-scheduler --vivado-bin D:/Vicado/Vivado/2017.4/bin
python -B tools/run_readstage_checks.py --work D:/f60-work/recheck-readstage
python -B tools/run_readstage_checks.py --case completion --work D:/f60-work/recheck-completion
python -B tools/run_output60_checks.py --work D:/f60-work/recheck-output60
python -B -m unittest discover -s tests -p test_video_protocol.py -v
python -B tools/audit_ddr_constraints.py --output D:/f60-work/recheck-ddr-audit.json
```

脚本默认从同仓库 `distortion` 读取未覆盖依赖。迁移布局时用 `--source-root` 指定其路径。XSim 脚本只修改临时编译副本中的 CRC include 路径。
