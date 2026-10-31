# HDMI V3 VS累计计数诊断（2026-10-30）

**本支线于2026-10-31按用户要求暂停。** 当前先推进摄像头目标链的处理/HDMI输出，暂不排查输入。本页下列“下一步”仅为历史，不再据此要求源线拔插或继续V3输入实验；参见[当前方向](ACTIVE_DIRECTION_20261031.md)。最近板卡和已封存结果见[当前交接点](CURRENT.md)。

17:22交接：板卡保持V3 `hdmi_uart_interval_diag` SRAM配置，Flash未写；当前输入仍不合格。V3首个10秒窗口20包累计VS计数均为0，PCLK/DE/快照持续新鲜，故障C5。已请求用户保持供电再拔插电脑端HDMI IN，等待明确完成反馈后只读复测，不再重复下载。

## 实现和版本

V2仅透出既有freshness；VS freshness回看100ms、UART每500ms采样，不能覆盖全部包间活动。V3额外透出监视器已有Gray计数的参考域解码值，未增加CDC链或改动帧判定。`dvp_mode_admission_monitor_activity_cdc.v`移除新增端口、assign和模块改名后，与原CDC监视器源码逐字相同。

| 字段 | 含义 |
|---|---|
| build tag | `0x48444903`，与V1/V2区分 |
| byte52 bit0..4 | PCLK、VS、DE、good-frame、snapshot freshness |
| byte53:54 | 小端uint16累计归一化VS上升沿计数，回绕65536 |
| byte55 | 保留零 |

其余包布局、64字节包长、CRC及尾标不变。计数从训练极性后的观察器使能epoch开始，并非独立于监视器的原始引脚采样器。对连续报告计算 `(new-old)&0xffff`，结合reference_ticks和使能/极性标志解释；不能将bad/good/frame freshness当作原始VS计数。

## 候选自身的实现证据

- 构建：`distortion/build/hdmi-uart-diagnostic/trained-pds-interval-1030-a`，18项来源/12份实际编译副本，退出0、无漂移。
- 审计：`distortion/build/hdmi-uart-diagnostic/interval-review-1030-a`，161同步FF、81对同址级间连接、46脚方向正确；74/92/1/4四组原生查询精确匹配。
- Scoped ADF：`35803de72be04a3fcde3bdf1d774ce6614d71a602ee1d2bd81c45c89bdcdc496`。双角十类零失败；slow setup/hold +1.151/+0.147ns，fast +1.996/+0.094ns；MPW均6.457ns。
- 最终5110单元功能图及所有寄存器位置与本候选原始图一致。例外仍限每角167条8ns max-delay、167条hold false path及各4条recovery/removal；setup false path为0。没有复用旧ADF或旧时序结论。
- 位流：`distortion/build/hdmi-uart-diagnostic/interval-bit-1030-a/generate_bitstream/hdmi_uart_interval_diag.sbit`，3,791,112字节，SHA256 `f254e26238a67fae7d48bbb2a810236e489d57f68672feb3ea6be1d315059bdc`。实际流程为新STA→运行时精确审计→生成。
- 下载回执：`distortion/build/offline-20261024/hdmi-interval-program-1030-a/receipt.json`，17:15–17:16，PG2L100H/ID匹配、DONE=1、Flash=false、清理无错误。
- 150项协议/评估器CPU回归通过；原生UART wire测试覆盖16bit回绕、小端、快照冻结、CRC；证据在`interval-uart-sim-1030-a`。

所有关键来源、原生报告/库、位流、下载脚本/回执及原始采集已封存在[214项证据](../distortion/results/hdmi-interval-20261030/manifest.json)，大文件采用gzip并分别记录压缩/原始SHA256。[本轮汇总](../distortion/results/hdmi-interval-20261030.json)明确输入失败，HardwareReleaseAllowed=false。

## 实测与下一步

首个10秒窗口20包、19个包间增量均0。flags05bf，初始化完成；faultC5，几何0×0，好/坏帧均0，freshness15。独立struct/zlib复解析与解码回执逐项相同。记录在`distortion/results/hdmi-interval-live-20261030/live-status-a.*`、`assessment-a.json`、`independent-a.json`。

V2此前重连后宽高1920×1081、bad绝对值28995，但窗口内不再变化；不能把这个绝对值当作合格视频帧数，也不能由最新V3窗口推断此前一直没有VS。

待用户确认V3运行时源线拔插完成后，用项目`.venv/Scripts/python.exe distortion/tools/hdmi_status.py --port COM7 --seconds 10 --output distortion/results/hdmi-interval-live-20261030/live-status-b-after-replug.json`采集。输出文件必须新建。然后用`assess_hdmi_input.py`绑定原始字节和回执生成独立评估，并统计V3累计VS增量。

如果累计VS仍停住，下一项检查源端当前模式、MS7200模式/锁定状态及VS引脚链路，或增加原始电平/HS活动观测；不改未知寄存器，不凭Windows显示配置或合成TX色条判定输入成功。已有PCLK和DE活动不能证明像素内容、PHY锁定或有效帧。外部AC、完整CDC/MTBF、DDR/畸变、长稳及温度仍未验收。
