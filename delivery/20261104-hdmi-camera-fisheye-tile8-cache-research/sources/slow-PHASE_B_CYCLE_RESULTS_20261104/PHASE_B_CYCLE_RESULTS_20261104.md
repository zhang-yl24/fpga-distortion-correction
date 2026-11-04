# 阶段 B：真实 bank/DMA 的周期事件与相位扫描

结论：**下一版先处理帧内 DDR/miss 等待，暂不把三源槽或第三结果 bank 作为第一项改动。** 本次新运行在真实原 bank/DMA 上复现了“处理约 44ms→35ms，仍为每两个刷新才接收一个新结果”；同一原调度在处理缩短到显示周期以内后，八个受测相位均能每刷新接收一个新结果。它支持先突破处理预算的优先级，不证明板上只改处理时间就一定达到 30FPS。

## 实际执行范围

独占新目录为 `output/tile8_next15h_20261103/new-next-probe-20261104/`。运行了 XSim，没有运行 EDA/PDS、串口、硬件，未修改任何生产或已发布 RTL。

实际编译原 `hdmi_camera_fisheye_bank_tile8.v`、`hdmi1080_input_dma.v`、`hdmi1080_capture_cdc.v`、`video_async_fifo.v`。四份原 RTL 的字节 SHA 均与冻结 `7b2c444b...40a8fb`、1038-input provider map 相符。真实 capture/DMA 处理像素打包、CRC、异步 FIFO、source_valid/ready 和 bank reserve/release；本探针没有独立像素 oracle，也不以其内部 CRC 一致性替代完整系统像素验证。

**明确的替身：** 引擎是固定周期计数 stub，不执行鱼眼映射、cache、DDR 源读和结果写。显示是完整 grant/done 所有权握手加固定 lease 时长，不实例化真实显示 reader/像素扫描。输入为 16×16，输入时钟约 148.5MHz、core 为125MHz，输入/输出周期按实际60/30的比例缩短1000倍。输出模型周期4167 core cycles，lease4000 cycles；原 CDC/DMA 的固定开销没有缩短，因而相对占比被放大。这是隔离调度机制的周期实验，不能称为完整1080p系统性能或实板FPS。

## 40 个真实完成的用例

权威运行是 `phase-sweep-b/simulation.json`：Passed=true、40案、InputDrift=[]、用时197.713s。五个引擎时长分别配八个输出相位（0/521/1042/1563/2084/2604/3125/3646 cycles）。每案都由真实 bank 计数证明 `last_cycles=requested_stub_cycles+1`，最终完整排空。没有改运行中的刺激或环境变量。

| bank 实测处理周期 | 按1000倍时间尺度换算 | 每案窗口刷新数 | 八相位的新完成显示 / 重复显示 | 相邻 source accept 间隔 |
| ---: | ---: | ---: | ---: | ---: |
| 5542 | 44.336ms | 16 | 全部8 / 8 | 全部8334 cycles |
| 4434 | 35.472ms | 16 | 全部8 / 8 | 全部8334 cycles |
| 4151 | 33.208ms | 16 | 全部16 / 0 | 全部4167 cycles |
| 3751 | 30.008ms | 16 | 全部16 / 0 | 全部4167 cycles |
| 3001 | 24.008ms | 16 | 全部16 / 0 | 全部4167 cycles |

这是原两源/两结果调度的实际 RTL 响应，没有增加队列或改准入条件。按输出模型30Hz换算的15/30档位仅表示上述有限模型的计数比例。receipt中的历史字段 `NormalizedBoardUniqueFPS` 也只是这种尺度换算，**不是板上新测量**。

新显示与重复按 `display_done` 落在 `[4×OP,20×OP)` 内计，刷新按同窗 `scan_boundary` 计，首尾 lease 可能跨窗，因此一般相位计数允许一帧边界差。独立分析已重新配对全部 display_grant→display_done 的 ID/bank，每次lease确为4000 cycles，并从完整事件流重算窗口unique/repeat，结果逐案等于RTL统计。更强的周期依据是表内相邻 source_accept：超预算8334，预算内4167，不依赖单个首尾租约的取舍。

## 同一 ID 的实际事件解释了改善为什么被等待吞掉

下表为相位0、ID4的真实 CSV 原始周期。两个时长使用相同DMA/bank/显示调度。

| 事件 | 旧时长模型5542 | 新时长模型4434 | 预算内模型4151 |
| --- | ---: | ---: | ---: |
| capture_grant | 16671 | 16671 | 12504 |
| source_offer | 18758 | 18758 | 14592 |
| source_accept | 25004 | 25004 | 16670 |
| engine_start | 25005 | 25005 | 16671 |
| engine_done | 30547 | 29439 | 20822 |
| pending_set | 30548 | 29440 | 20823 |
| pending_clear = 首次display_grant | 33338 | 33338 | 20837 |
| 首次display_done | 37338 | 37338 | 24837 |

5542→4434少了1108处理周期，但pending等待2790→3898，恰好多了1108；首个新显示grant/done没有提前，source_accept也没有提前。这是本模型的**已测周期关系**，不再只是从平均FPS减处理gauge得到的残差推断。4434→4151则跨过本相位的刷新预算，pending等待降到14周期，源接收间隔由8334降到4167。

grant→offer约2087/2088周期；offer→accept在ID4为6246或2078周期。offer等待与processing/pending/display lease互相重叠，不能把累计等待计数相加成新的“总延迟”。源frame ID由真实DMA grant递增，不是每个输入光栅都会获得ID；no_grant汇总含warmup与drain，不是测量窗的异常drop计数。

## 对下一版的实际建议

1. **先等待完整1080p持续系统profile完成，并据真实AR→首R、beat gap、cache FSM、源offer/accept与display事件进一步确认。** 该工作由队友在独立 `output/new-next-probe-20261104/system-profile-a/` 运行，包含真正引擎、DDR竞争和像素oracle；本报告不预借其完成状态。
2. 当前35.45ms实板处理gauge已超过33.33ms。本探针说明原调度并不在所有预算内情形都硬性锁死15FPS，因此下一候选优先减少DDR/miss串行等待、需求优先浅预取或完成时序修复的cache方案，目标持续处理约30ms并保留交接余量。仅消除一个小控制空泡不够，也不能只把一个样本压到33.30ms就宣称成功。
3. 当完整系统或新板测已满足处理预算，却仍随输入/输出相位出现重复/准入损失，再推进三源描述符队列；第三结果bank是另一路所有权问题，分开A/B。队友三源模型可借鉴，但本次没有实施它。
4. 本探针只扫八相位、固定lease、五时长和缩小几何，不覆盖异步长期频差、真实输出FIFO/DDR竞争、随机处理时长抖动，不能据此宣布调度已“充分证明30FPS”。

## 可复核文件及失败刺激记录

- `phase-sweep-b/simulation.json`：实际40案工具回执，逐案summary/event/log原件。
- `phase-analysis-a.json`：独立重新核对源身份、逐ID实际引擎时长、完整lease配对与分组结论。
- `phase-timeline-a.csv`：每案每ID的grant/offer/accept/start/done/pending时刻及区间。
- `tb_phase_probe_a.sv`、`run_phase_probe_a.py`、`analyze_phase_probe_a.py`：新增探针和分析源码；生产RTL未改。

探索失败全部保留：smoke-a为bench超时常量被32bit截断；smoke-b为测量结束时过早停止显示请求，不能排空；phase-sweep-a因两个initial读取同一plusarg时stub未按请求改变，实际bank计数揭露后已中止，不作时长A/B证据。最终版本在复位期显式设置stub时长，并在RTL及runner两边要求真实计数为request+1。smoke-c仅其单个4433周期用例有效。它们均为刺激/探针问题，不记作冻结DUT失败。
