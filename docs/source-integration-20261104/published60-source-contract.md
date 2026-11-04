# 已发布 60 帧源码契约与最小整合单元

审计对象是 PR25 / `codex/fisheye60` 的精确提交 `25015cf3b2c1c31d7940828ac583d5d1eb6feeb3`，不是正在构建但未发布的 `scout-local-a`。后者和当前 KEY1 工作均未知，本轮不读取 D 构建树、不建立竞争 KEY1 候选、不执行 EDA 或硬件操作。原 PR28 入口仍保持回退。机器可读的完整路径、模块、行号、Git blob/SHA256 及 116 输入清单见 `published60-source-contract.json`。

## 身份和构建边界

- 最终 I 阶段：116 输入，source identity `d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5`，BuildID `11037003`、ProfileID `ed59f83e3cfbc77b`。其中 75 个为 DDR 生成/IP 输入、71 个为 `.vp`，不属于纯自研源码。[状态及身份](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/VALIDATION_STATUS.json#L1)
- 原始 `rtl/` 仅有 19 个 overlay，不能直接代替已验收身份的编译输入。构建器将 top 的 `INPUT_TIMING_CONFIGURED=0` 改为 1、BuildID `11036003` 改为 `11037003`，将 engine 设为 INDEX10/9、上路 rowpad、640/440 行和 8×8 tile，并重定位 include。默认 raw 参数和最终准备后参数必须分别记录。[精确准备逻辑](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/tools/prepare_candidate.py#L11)
- 顶层模块 `hdmi_camera_fisheye_top`；`hdmi_camera_fisheye_system_c.v` 实际模块名为 `hdmi_camera_fisheye_system`。core 125 MHz，输出直接转发 `pixclk_in`，约 148.5 MHz 和 2200×1125 扫描得到 60 Hz；这不证明每秒 60 个新校正帧。[时钟及顶层实例](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi_camera_fisheye_top.v#L55)
- main 比对基准 `8f2a5b7679ca77153bd36d52a2660e286bff7730`；新 main `327ef108f48b467b8bbe5c4e67f9b503e4983b50` 只改变 `submission/`，因此 RTL 比对仍适用。O/P 为 `1b9727e31f690a2598ab51cdb27ba645c0d5eda5` 的精确 native/source 路径，不能用同名 peer 实现替代。

## 图像、DDR 和参数

保留 C 的 OpenCV fisheye k1/k2/k3/k4、balance 0.5、零旋转、Gamma OFF；完整 K/D 浮点值、Q8/Q30 定点头及径向表 SHA 均在 JSON。Profile 头 SHA256 `2814df34b94fb3de08fbe03abbe2dfff2a3062bd85ef67e6a437a4c234ea769b`，径向表 `e7a909761547a68ecc1b424e14d2592fc91918101d0b9e309081ac757cc6de3f`。它不是 Brown 参数或旧 OV5640 标定。[标定头](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/distortion/board/hdmi-camera-fisheye-profile.vh#L1)

RGB888 经两级全范围 round(v×31/255)、round(v×63/255) 量化，再以 RGB565 帧存；每个 256 位 beat 含 16 像素，先到像素位于低 16 位。坐标为 signed24 Q8，四邻域双线性，越界邻点为黑。两路分块写回由 writer 恢复成 raster，外部 `RESULT_TILED=0`。[量化](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/distortion/rtl/experimental/hdmi_camera_rgb565_quantizer.v#L1) [打包](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi1080_capture_cdc.v#L58) [采样](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/ddr_remap_sample_scatter4_rowpipe.v#L18)

| 项目 | 精确契约 |
|---|---|
| DDR UI | 28 位、4 字节地址单位；256 位 R/W；32 位 strobe；4 位 RID；无 RREADY、无 B 通道 |
| 帧槽步长 | `0x100000` 单位 = 4 MiB；完整帧 4,147,200 字节 |
| 逻辑源槽 0/1/2 | 物理槽 0/1/4；字节基址 0、4 MiB、16 MiB |
| 结果槽 | 物理槽 2/3；字节基址 8 MiB、12 MiB；预留总范围 20 MiB |
| DMA 写突发 | 16 beats；beat0 可与 AW handshake 同拍转移；WREADY 接收、返回 WLAST 检查 |
| cache | 每次 8 beats/256 B；上路 256 KiB rowpad、下路 128 KiB 线性；rowpad 不改变真实地址 |

地址、容量和握手来自 [DMA](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi1080_input_dma.v#L1)、[银行映射](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi_camera_fisheye_bank.v#L26)、[cache](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/ddr_neighbour_cache_scatter4_rowpipe.v#L114)。禁止把 4 字节地址单位误当字节，也不能截掉源槽编号高位。

## KEY1 和描述符的真实边界

KEY1 低有效、两级同步，125 MHz 域按 2,500,000 拍分别确认 release/press，默认 corrected，复位时一直按住不会立即触发；每次合格按下只切换一次。它输出的是请求。[KEY1 状态机](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/camera720_view_control.v#L1)

DMA 的两项 head/tail 描述符只含 `bank[1:0] / id / crc / pixels`，**没有 mode 字段**。`source_commit` 是 system 在 core `src_valid && src_ready` 边沿对该描述符的实际处理接收回执，不是采集结束或 tail 入队事件。bank 此边沿将 `cfg_corrected` 锁入 `active_corrected`，engine 再在 frame handshake 锁入 `cfg_hold`，mapper 只在旧坐标完全排空后配置。故能保证一帧处理模式一致，不能声称采集时或入队时的模式随描述符锁定。排队期间按键会影响下一次真正开始处理的帧；同边沿请求翻转按非阻塞时序由本次接收读取旧值。[两项描述符](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi1080_input_dma.v#L44) [模式锁定边沿](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi_camera_fisheye_bank.v#L64) [engine 锁定](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi_camera_fisheye_engine.v#L122)

结果/显示描述符也无 mode 字段，UART 和 LED 显示 `corrected_requested`，不是当前展示帧的 applied mode。切换后请求已稳定的 UART 窗口仍可能包含旧 pending/front 结果，必须有排空边界或独立逐帧 mode/ID 证据，才能将窗口 FPS 归于该模式。后续若要采集时语义，必须显式扩充 head/tail、处理、结果和显示元数据并重新审查；本轮只提出契约和离线验收计划，不实现第二个 KEY1 版本。

## 停顿、故障、排空和复位

DMA 等待完整像素数、CRC、全部 DDR 写拍和 FIFO 排空后才提交；停顿的 head 保持，消费时原子提升 tail。引擎需两 lane 的 ID/base/CRC 完成且读写总线空闲，才发布整帧。结果的 display lease 还需 reader/pixel 的 ID、epoch、bank、CRC、计数、good 全通过，reader 空闲、FIFO 为空、grant ACK 和实际银行释放边沿仍健康。故障锁存后隔离 lease，不能先释放后补验。[提交及尾项提升](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi1080_input_dma.v#L167) [双路整帧完成](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi_camera_fisheye_engine.v#L126) [实际释放门禁](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi_camera_fisheye_system_c.v#L178)

已发 ARVALID 必须保持到 handshake；新故障不能撤回 AW/W。运行时只停止接收，DDR、capture、FIFO、consumer 的共同 reset 才重建 epoch。PCLK watchdog 只检查时钟存在，不证明 VS/DE 或帧进展。[保留已发 AR](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/ddr_neighbour_cache_scatter4_rowpipe.v#L226) [运行复位边界](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/hdmi_camera_fisheye_top.v#L182)

## 与 main/O/P 的精确关系

19 个 60 overlay 与 main/O/P 的原文件均非同 Git blob；有些仅综合属性改变，有些是真接口/架构改变，逐项见 `published60-module-comparison.json`。物理 116 输入中，main 有 10 个模块精确同 SHA256，O/P native/source 有 5 个，包括 `bilinear_rgb`、读/写仲裁、`mul32_pipe`、CRC；O/P UART 发送器另有同 blob 证据。

main raw mapper 与 O/P `stable30-OP/native/source/profile/...mapper.v` 仅第 14 行 include 根不同，都有 `cfg_valid/cfg_ready/in_valid/in_ready`。不能笼统宣称这些 mapper 缺握手。被比对的 O/P `geometry_ab` system/bank/engine 另有 Gamma、Brown/旋转等 17 个配置字段；60 是固定 C profile + `cfg_corrected`，即使 module 名或 source_commit 相同，也不能整套替换。

三版 source_commit 边沿与 ID/CRC/pixels 语义相同；60 的 source/released bank 为 2 位，main/O/P 为 1 位。逻辑源槽 2 映射物理槽 4，截断会别名到源槽 0、破坏所有权。source_commit 与 `result_publish=source_release` 是不同事件。新 main 的报告更新没有改变这些源码。

## 最小下一步：隔离的读返回单元

建议在新的 integration 目录只组合以下单元作 source-only 评审，不恢复旧工程入口，不接板级 top：

| 源 | Git blob | SHA256 |
|---|---|---|
| 旧 60 `rtl/ddr_read_return_register.v` | `504d127378dc7a2633fa916f54baf0408d3f9081` | `bb106a1b03d30f041b0b38eba2a687bef7fb54afa457d06f833d57787fae3427` |
| main/OP 共同 `ddr_read_arbiter.v` | `dad2ea07876ad11cfeb15bca21a845d043eb639e` | `59283dd5d5d292cf8dd6d1bff51b565c13357ce94bdead0d467421604c5f72be` |

stage 在 current main 中不存在。仲裁器必须是 main `distortion/rtl/ddr_read_arbiter.v` 或 O/P `stable30-OP/native/source/rtl/ddr_read_arbiter.v` 的上述精确字节，不能换用 peer fill8r2 的不同实现。

wrapper 只连线：两客户端 AR/R 接原仲裁器；仲裁器公共 AR 直达原 DDR，同时将此公共 `arvalid/arready` 供 stage 观察；raw DDR R(data256/valid/last/id4) 经 stage 一拍后接回仲裁器 R。**不门控、不延迟、不撤回 AR 命令或 ARREADY**。raw 首拍可与 AR 接收同拍，下一周期由已锁定仲裁 owner 接收；连续返回仍每拍一个。没有 RREADY、没有 flush；payload/last/id 寄存器不清零，只有 valid 决定是否有效。共同 `rst_n` 在正沿同步采样，不允许用 fault 生成隐式运行复位。[stage 全部逻辑](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/rtl/ddr_read_return_register.v#L1)

分别导出 `return_protocol_fault/return_fault_code`、`arbiter_failed/arbiter_fault_code`；组合 failed 仅 OR，供父系统停止新接收并隔离当前 epoch，不能反馈 reset 或命令门控。guard 无主返回 `0x40`、重叠地址 `0x41`；仲裁器超时 `0x01`、RID/RLAST 错 `0x03`、无主 staged R `0x04`。guard fault 为正沿注册 sticky，不能当作 raw 故障对父级 release 的零周期否决；同沿 raw fault/release 必须另做新整机审查。若 wrapper 选择 guard 优先的组合 fault，这是明示诊断规则；原 TB 使用 arbiter 优先，不能继承并发故障优先级的验证结论。

已发布 TB 全文和 5 个原始源的 hash 在 `published60-readstage-unit-sources.json`：`tb_legacy_registered.sv` → `tb_ddr_read_arbiter`；`tb_readstage_integration.sv` → `tb_ddr_readstage_integration`；`tb_readstage_guard.sv` → `tb_readstage_guard`。前两直接实例化 stage+arbiter，**未实例化新 wrapper**。保留原文件，新增 wrapper 端口等价和同时双故障导出检查作为待跑验收；本轮没有调用 HDL 编译或仿真。

技术结论仅为：精确匹配的两个单元和上述纯连线方案适合隔离 source-only 组合评审。还不能称 wrapper 已编译、full-system build、时序改善或实板通过。

## 已有证据与本轮验证

I 阶段已发布全帧模型：2,073,600 像素各两组零差异、CRC `04f1ed35`；latency12 为 1,692,988 拍、latency40 为 2,076,702 拍，125 MHz 换算 73.834/60.192 FPS。小帧整机两次 epoch 共 32 个唯一显示帧、151,552 显示像素、零欠流/差异。这些是绑定旧 I 源码的数字证据，不是 scout 或板上 FPS。[模型与整机证据边界](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/README.md#L23)

物理仍 FAIL：slow core setup −2.886 ns、pixel −2.414 ns、core→PHY0 −0.012 ns、cfg→board27 −0.331 ns，另 recovery −0.403 ns；外部 IO、held-bundle CDC/复位、60/600 秒实板验收未完成，无新 60 位流。Gray 的 34 路径/4 skew 组 6 ns、同步器结构及 DDR 约束审计等通过子项不能替代整体签核。[物理失败及剩余项](https://github.com/zhang-yl24/fpga-distortion-correction/blob/25015cf3b2c1c31d7940828ac583d5d1eb6feeb3/delivery/20261103-hdmi-camera-fisheye-60/VALIDATION_STATUS.json#L75)

本轮独立重算 55 个读取文件的 Git blob SHA，全部匹配；23 项 raw overlay 的 SHA256 匹配发布清单；116 项物理 SHA256 清单重算 aggregate identity 匹配 `d931…`。另 64 个 main/O/P 比对源码由子审计独立重算 Git blob，零失败。未下载并重新哈希全部 116 个编译/IP 字节流，未执行源闭包重建；这个限制已写 JSON。额外 5 个最小单元素材逐一验证 blob/SHA256。

原始 UART decoder 的纯 CPU 测试本轮 **27 passed**；只证明字节协议、身份拒绝、计数/模式窗口处理，不具硬件意义。详情见 `published60-offline-verification.json`。其他 HDL、EDA、上板验证均未跑。

## 下一步离线验收计划

1. 以未来发布的精确 KEY1/scout SHA 重新绑定；不把旧 PR25 替代当前构建。
2. 在 source_ready 停顿和 head/tail 满队列时切换请求，检查 bank/id/crc/pixels 不变，并核对处理接收边沿才锁 mode。
3. 覆盖接收边沿前/同拍/后切换、全帧双 lane 一致、坐标/输出/DDR/末像素反压与完全 drain。
4. 注入 fault/reset、重复/无主完成、ACK 停顿、晚到故障和 FIFO 重新出现数据，禁止假释放、假发布和统计增加。
5. 读返回单元覆盖 1/2/8/16 拍、AR 停顿、同拍首返回、连续/间断返回、lastR+nextAR、无主/重叠、RID/RLAST、超时、共同 reset；另验新 wrapper 的连线及组合 fault 优先级。
6. 离线 RTL 通过后，未来板级候选仍需新整体物理时序、CDC/IO、精确位流和实板新帧率验收；本报告不授予这些状态。
