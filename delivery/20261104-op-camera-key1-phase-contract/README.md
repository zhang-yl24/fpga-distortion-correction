# KEY1 摄像头输入：相位契约与 RX 校验候选

**SOURCE_CANDIDATE_PNR_RUNNING：本次先交付源码候选。Map 已 exit0；截至 2026-11-04 16:43（UTC+08:00），同一 N 工程仍在 PNR，尚无本轮最终 STA 或位流。现场 1919/0x12 根因、摄像头、实体 KEY1、校正新帧率、端到端延迟和外部 IO 均未验收。旧父位流／时序报告不能冒充本轮结果。**

基于已发布 cf9 KEY1 版本，位流 SHA256：
cf9fcf563f7487bafccf083f5ad83f7e94c18759beea3236187e32c8b2c66731。
源码／位流父提交为 8c3fe2a05ae56e3338a495f5085d489506352439；本包只针对四份列明 SHA 的文件。父源码里若缺少板级依赖，请由操作者提供相同的合法原件，不从本包补齐厂商 IP。

## 四文件改动与生产配置

- 既有 27 路输入寄存组请求局部 syn_useioff=1，FPGA 仍用 pixclk_in 的 posedge，不增加使能或复位门控。本轮放置表已显示实际 19 路 IREGIS（DE/HS/VS＋RGB565有效16位），其余 RGB 低位被裁剪；PCLK K21 为 NA，因为它是时钟。27位源码统一 posedge 不变，不能称27路全部打包；放置证据也不是最终外部 IO 时序签核。
- MS7200 寄存器 0x1281 采用完整 READ→masked WRITE→READ verify。生产 wrapper 默认 PCLK_INV_BIT=0，执行 (original & 0xfb) | ((bit & 1) << 2)，仅改变 bit2，另外七位保持；末次读回必须整字节等于 expected。
- 接收端保留原单一 I2C bus owner，必须取得真实 ACK、读字节有效及 STOP 完成证据后才交接 TX。NACK／X、无效读、读回不符或超时不能放行；在途地址／数据／方向保持到原交易完成，不用局部复位撤销交易。
- 原 RX 311 项表和原驱动状态／时序尾部保留。1920×1080 资格、DMA、KEY1、bank／cache／writer 保护不删，不增加假定 IO delay 或宽泛时序例外。

注意 leaf 模块 ms7200_ctl_phase_contract 的参数默认值仍为 1；正式路径由 ms72xx_cfg100_ctl 的默认 0 显式传入。不要脱离 wrapper 单独实例化 leaf 后宣称得到生产 bit2=0 配置，也不要另行改成 negedge。

## 便携补丁与编码

本包发布四文件的窄改补丁，不重发完整寄存表、旧驱动主体或厂商依赖。

原 I2C 文件是 GB18030；原采样 include 使用 CRLF。冻结候选全部为 UTF-8/LF。因此补丁只适用于明确转换后的 UTF-8/LF 基线，不能承诺在原始编码文件上直接 git apply。身份文件分别记录 original／normalized patch base／candidate SHA。

1. 从 cf9 的合法 native 源码独立副本中准备四文件 patch base：
   python -B tools/prepare_patch_base.py --source-root /path/to/cf9/native --output /path/to/new-review-copy
   工具先核四个原始 SHA，只向全新输出目录写四文件，不修改 source-root。
2. 在 new-review-copy（含 native/）执行：
   git apply --check /path/to/integration/PHASE_CONTRACT_UTF8.patch
   git apply /path/to/integration/PHASE_CONTRACT_UTF8.patch
3. 将四份输出的 candidate SHA 与 SOURCE_DELTA_IDENTITY.json 对比，再在独立完整工程中整合。这四条目标文件路径不变，wrapper 已连接新模块名，不要额外把旧／新两份同一模块同时加入编译。
4. 本交付准备已在隔离副本实际 check／apply，并确认四份最终文件逐字节匹配冻结 candidate。准备工具仅作 Python AST 检查，不声称本轮运行了新 HDL 仿真。

## 已有离板证据与未完成项

final-d 的 5 阶段正式 xsim 全 exit0，覆盖两个 bit 设置、256 个原字节保持七位、读取有效、三阶段 NACK、超时／reset及真实 RX driver wrapper 的 owner 交接。原输入 SHA 不变，模拟器子树已退出。

独立 vendor-model-b 传播模型的 3 阶段也已通过：148.5MHz、40%–60% duty、inv0/1、27 路和独立 RGB oracle。它仍是假设传播模型，不是 PCB/芯片交流参数保证或现场证明。旧 handoff 内 NOT_VALIDATED／NotPerformed 等字段未随新结果更新；本包引用分别重算 SHA 的新 RESULT，不修改或追认旧失败记录。精确范围见 VERIFICATION_SUMMARY.json。

本机旧 cf9 两轮 PC HDMI 均 good=0、主要宽度1919、启动资格未放行；摄像头只在同学处，没有可比较的相机原始串口日志。既有结果不能算摄像头故障复现。新相位设置的现场效果、最终 STA 和完整业务通过仍须以本轮独立最终产物及真实采集决定；目前19路 IREGIS仅是放置证据。

## 回退身份与边界

回退使用同学自己现场已经验证、且保留原件的版本，下载前核对完整 SHA 和器件。优先选择：

- a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547：用户反馈同学摄像头现场测试成功的原 PGIQ 诊断版，不含 KEY1 切换或本轮相位契约；原 slow setup 仍有 4 个端点违例、WNS −0.032 ns，未签核。我们没有其摄像头原始采集记录，不把口头成功反馈扩大成稳定性或 60fps 验收。
- 同学自己已验证的 15fps 版本：用户记录的完整 SHA256 为 aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b，现场仍须核对自己保存的原文件，不能替它编造本轮复测。它是原 15fps 回退，不代表本轮新配置或 60fps。

cf9fcf563f7487bafccf083f5ad83f7e94c18759beea3236187e32c8b2c66731 仅是本候选的代码／构建父版；本机 PC HDMI 启动资格失败，没有证据将它列为可用摄像头回退。本包不重发上述回退原件，也不替现场操作者选择未知文件。

## 同一构建的当前身份

同N原始150输入清单 SHA256：
0c1b7e1bf0f08415b7539cccbcb7c6f413363956304a2d35b58f34d4772b9347。

完整150输入清单仅在本机逐文件核验，不在本目录披露其内部路径或 vendor/IP 依赖条目。上列 SHA 仅是不透明清单身份，供持有相同合法依赖的操作者比对；本目录只交付四源第一方窄改及必要实现摘要。四份候选源码与冻结 final-d 逐 SHA 相同。PDS 2025.2 ADS / build 211867，PG2L100H-6FBG676，编译标准 SystemVerilog。自行构建须显式使用 compile -verilog_standard SystemVerilog，并提供匹配且合法的其余板级／IP／约束输入；本包不是厂商依赖的替代品。

Map 已 exit0；放置阶段观察到19路IREGIS。这里只给截至16:43的未终态进度说明，不发布完整引脚位置、内部实现清单或拥塞明细，也不是最终 STA。后续完成后再追加同一构建的位流、最终 ADF 身份和六类检查×两角的真实报告；如仍有违例会保留实际失败路径，不使用父版报告补齐。

## 最短现场验证步骤（新位流发布后）

源码先给同学审阅／自行构建，当前目录没有本轮新位流。取得实际位流后先核完整 SHA、器件／引脚、输入模式和可用回退，只作 SRAM 下载，不写 Flash。

- 串口是继承的 PGIQ0001，被动84字节、115200 8N1；使用同学实际识别出的串口，不猜 COM。不要按 PGSTAT02／SGA／SGT 主动协议发送命令。下载前开启采集，保留完整原始字节、实际 bit SHA、输入模式与操作时间。
- 等 RX/TX 初始化，按真实状态观察48次连续好帧（间隔小于50ms、bad不增）的启动阶段；之后会有一次64个27MHz周期的观察器复位，good可能归零重建，再检查 startup_armed／qualified／release。通常初始化加此阶段可能需十余秒，不能盲等固定秒数或仅要求 live good一直≥48。
- 看 PCLK、good／bad、live宽高、qualified、release 和 fault；first_valid=0 表示live，不代表通过。只有业务已释放、显示有效后才验证实体 KEY1。
- KEY1 请求在 RAW／CORR 间切换，低有效／20ms去抖，在 source_valid&&source_ready 时锁入后续帧；不切换两个物理输入。RAW仍经RGB565结果bank，LED6只表示请求态。此功能未在本轮现场验证。
- [既有同协议解析器](https://github.com/zhang-yl24/fpga-distortion-correction/blob/f8f58a161111ecbac3400d0629a5064d43c405d8/delivery/20261104-op-camera-input-diagnostics/host/decode_runtime_diag.py) 已核3024B／SHA256 3c9537ad57725cedd421b64acaa624e52803cda43e9ef45ba4769b5d69e6c610。此PGIQ流没有模式／业务FPS／呈现率／端到端延迟字段，不能据它直接宣称新帧率或E2E通过。

本轮原生构建由主工程独占执行；本交付仅整理已有源码／证据，没有运行新仿真或EDA，不操作COM/JTAG/Flash。现有回退版本不覆盖。
