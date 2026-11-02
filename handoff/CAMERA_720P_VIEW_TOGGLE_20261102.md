# 720p 原图／矫正一键切换（2026-11-02）

用户要求先实现运行中的一键切换，提帧任务后置。基于 `main` 的 `11d61c1fe2090b75b7b26bac8132bdf577be4cc4`，工作分支为 `codex/camera720-view-toggle`。

## 最新实板结果（15:15后）

切换版已实际下载成功，当前本板 `camera720_view_toggle_top`（BuildID `47e52e93b7238f29`），默认矫正。SRAM下载15:12:37–15:14:27，DONE=true、Flash未写、CleanupErrors=[]。位流SHA256 `0ca6d19bf074c73cba0346a22e54ba3afb99a595728e6420a1cbb767b963dfe5`，3791112字节；final ADF f31e112a…338ff2d。下载后30秒UART为30包/29有效窗口，435接受/435处理/435唯一输出，均15.0fps，0身份不符/拒包。用户现已确认“切换没问题，可以推送”，原图／矫正实屏切换验收通过；LED状态、全视场光学与横纹定因不在本次反馈范围。新证据包见[实板封存](../distortion/results/camera720-view-toggle-live-20261102-a/README.md)。

CPU100项通过、full-b3686400实际显示像素匹配、最终双角十表/130引脚电气/2486CDC case/fresh bit gate均通过。位流authority-c完整重算后封存2042项依赖，program-a计划2069项绑定。没有调整画质参数，没有提帧。用户已授权提交并推送当前成果分支。

## 操作设计

- KEY1（C23，低电平按下）每按一次切换原图／矫正；默认矫正。
- KEY0（C22）仍是复位。长按 KEY1 不连续切换，稳定松开后才接受下一次按下；复位时按住 KEY1 也不误切换。
- LED0 表示请求模式：亮为矫正，灭为原图。画面须等待下一完整处理帧和显示边界，因此 LED 可以稍先于画面变化。
- LED5/6 仍是采集／处理计数，LED7 仍是故障指示。
- 1280×720 画面仍居中于现有 HDMI 扫描区域。原图选择完整的精确 identity 参数，不只是把畸变系数清零；当前校正参数、相机配置、方向和时钟保持。

KEY1 电气依据为 `hardware_check/hardware-guide.txt` 的用户按键表（2168–2190 行）；新候选增加独立输入与内部上拉，当前基线 C23 未占用。

## 实现

新增 `camera720_view_control.v` 在 125 MHz 核心域完成两级输入同步、20 ms 去抖和模式翻转。`camera720-view-select.vh` 选择原图或当前镜头整组参数。既有 `rotated_remap_core_gamma_scatter4` 的 `accept_frame` 将所有映射参数一次锁存；处理过程中改变请求不会改写该帧，结果 bank 仍在完成且校验后发布，HDMI 仍只在帧边界取得完整 bank。

旧物理证据与冻结源码未改写。`camera720_view_toggle_build.py` 将统计版 build-c 的完整已绑定源码闭包复制到独立目录，生成新 top/FDC，并增加选择头文件和按键模块。`camera720_view_toggle_native.py` 只用于新 ADF 的只读导出／查询，不允许生成位流或下载。

## 当前验证状态

- 按键 RTL 实际 XSim 仿真通过：短毛刺、按下／释放抖动、长按、往返切换、按住复位、单周期脉冲，去抖参数 4 和 1。
- 全系统 full-b 三帧“矫正→原图→矫正”已通过：实际显示3686400像素（3唯一帧+1重复帧）逐像素匹配独立参考，4次CRC、背压、处理中及pending时改请求、bank复用、final drain齐全，欠流/CRC错均0；2729.073秒，来源和fixture无漂移。full-a异常退出原回执保留，不能算通过。
- 新物理最终候选已通过：独立hold支路绕行、精确reset、fresh双角十表、130引脚/电气及2486/2486物理CDC case均通过；10个fresh小批次+1个IO查询收据全部Passed，原超时大批不参与证明。最终ADF为f31e112a1764d8175cce5cac013c2611b4032ebcd615219c3dfc763cf338ff2d。位流前完整复核、生成、最终verify及SRAM下载均已通过，见顶部最新实板结果。
- 当前板上已为切换版，下载后新UART独立测得15.0fps；旧统计版回执作为历史回退保留。

本次不需要重新标定或采集整套棋盘。用户已确认 KEY1 往返切换正常；下载、实屏切换与尚未确认的 LED7/横纹观察分别记录。

## 用户新增画质观察（切换版下载前）

用户表示将离开一会，检查完成后继续授权直接上板；同时感觉 720p 清晰度下降，并能看到“明显的横向弯曲条纹”。用户明确暂无需调整画质，仅要求分析。该观察发生于切换版尚未下载时，不能归因于新切换功能。

后续澄清：是**细密横纹、不影响画面内容、非静止而在振动**，没有确认宽明暗带或图像断层。不能把宽明暗带频闪假设当作已识别故障；需原图／矫正对照后再区分照明、行噪声、采样与重采样纹理等来源。

暂不改变相机曝光、增益、防频闪、镜头参数或插值。待原图／矫正运行时对照，区分明暗条带（照明／逐行曝光等可能性）与像素错位／断层（采集或存储链路问题）。弯曲本身可能由几何映射改变已有条纹形状，不能单凭描述认定原因或宣称画质验收通过。

只读对照确认：

- 旧 VGA 正立版 `0x3821=0x06`，720p 为 `0x07`，后者打开水平 binning；OV5640 手册 3.2 节说明 binning 在 ADC 前平均相邻像素电压。它可能改变细线锐感，但不能据此认定本次振动条纹的根因。
- ISP 缩放控制 `0x5001` 从 `A3` 变为 `83`；这两种模式不只是输出宽高不同。当前确实处理完整 1280×720，不是早期 160×90 放大预览。
- 旧 VGA 图像 640×480、当前 1280×720，均逐像素居中于 1920×1080 HDMI 扫描，现图更大。
- 当前矫正中心约 `480/319.46≈1.50` 倍，旧 VGA 约 `240/159.56≈1.50` 倍；双线性插值和 RGB565 也是共同因素。不能把它们单独说成相对旧矫正版下降的新原因。
- 锐化表 `0x5300–0x530B` 两版一致，没有证据说主动关闭了锐化。尚无当前曝光／增益读回，不能确认长曝光拖影。
- 15 fps 与旧 VGA 粗估 23–25 fps 的差别影响运动连续性，不等于静止空间分辨率降低，也不充分解释振动细横纹。

依据：`hardware_check/ov5640-datasheet.txt` 第 3.2 节及寄存器表、旧 `ov5640_cadence_upright_init.v` 与当前 720 序列、两版实际镜头参数头文件、`rtl/bilinear_rgb.v`。光源闪烁可在逐行曝光相机产生横纹这一通用机制另见 [相机厂家说明](https://support.avonic.com/support/solutions/articles/80001175962-cmos-sensor-characteristics)；本机尚未验证该机制，不能将可能性写为结论。

## 新对话接续（2026-11-02）

从用户提供的原对话及仓库断点继续。开发优先级、检查通过后直接SRAM下载授权、暂不改画质参数均保持。未访问另一条HDMI输入路线。

新增可重跑的候选工具：原native收据绑定、精确hold route应用及完整路由验效、final inspector、精确reset apply/effect、CDC/IO候选审计及diagnostics处置。四个交付基线CPU审计通过；52条原生缩位诊断原件保留，与stats-delay基线逐字（仅源码前缀规范化）一致，11公开计数器事件、2受保护vendor事件的边界依据分别记录，受保护内部边界未独立证明。新按键计数器22位/2500000周期边界已验证，无新增缩位诊断。

未执行的hold-route-a/b计划保留，不作为结果；b因验证器完善后自哈希漂移被拦截，无native执行。实际成功为hold-route-c。CPU相关验证阶段计数以测试日志为准，不能叠加重复运行次数。当前系统仿真完整passed；仍需最终时序、130引脚及完整CDC、位流生成前检查，之后才允许下载。

## 最终物理候选复核（2026-11-02，新对话）

`hold-route-c` 后的 `repaired-export-a`（131.745秒）与 `repaired-route-a`（80.805秒）均实际通过。`reset-save-a` 96.841秒成功，仅应用重新推导的5组127source/endpoint精确reset例外；最终ADF SHA256为`f31e112a1764d8175cce5cac013c2611b4032ebcd615219c3dfc763cf338ff2d`。

`final-export-a`、`final-route-a`均fresh原生通过；`effect-a.json`全量audit及verify通过，SHA256 `a86cc36b6255433f71f54d6ed1d062db2b56ac672ef3ec57649486c762b5036e`。setup slow/fast +0.249/+3.100ns、hold +0.059/+0.020ns、recovery +1.164/+3.522ns、removal +0.353/+0.040ns、MPW +0.035/+0.035ns，十表全零失败。

39625单元、18596 FF位置、36308路线全部保持；原KEY1 pad到首同步级8条false-path原生变体逐SHA保留，16节其他例外不变。精确reset scope的127source/endpoint按capture clock展开为245逻辑check；实际edge变体另见机器记录，不能混用不同口径。

首次reset effect driver的失败回执保留：校验器误把两个同源跃迁捕获变体当成应覆盖r/f两种源跃迁。只修改独立effect解析器，严格比较原始before/after路径多重集后重新全算通过，未改native数据库或源FDC。

14:08左右COM7只读6秒确认板上仍为旧统计版e396af749d6e350d，6包/5有效窗口，接受/处理/唯一输出均15fps，0身份不符/拒包，UARTTransmitBytes=0；尚非新版本实测。

最终100项CPU回归通过（31.01秒，final-cpu-tests.xml）。最终物理查询1139项，38组额外时序命令；原38组单进程超过300秒上限，失败回执不用于证明，成功IO收据173.876秒保留。后改为4组一批的10个fresh原生批次、3路并行，逐条确认38组命令无漏无重，源ADF均f31e…ff2d；完整proof仍待这些批次全通过。原超时PID30768的普通权限清理曾失败，后依据原OwnedPID+路径+启动时间精确清除其进程树，独立cleanup回执保存，未按进程名清理其他任务。

## 最终CDC与IO结果

`cdc-final-proof-b.json`：ScopedDigitalChecksPassed=true，ExpectedCases=ObservedCases=2486，Missing=[]，Violations=[]，1044项输入绑定、InputDrift=[]。130引脚均经源/FDC/原生网表/路由位置与电气属性核验；40个DVP conditional case、完整HDMI TX maxima、UART实际launch均覆盖。KEY1两级同步实际打包在同一BLE；DirectInternalRows记录精确Q→D、独占首级扇出、同clock/reset，依赖当前vendor packed sequential model与独立full STA，不伪造无法逐FF报告的独立slack或analog MTBF结论。

十个时序shard加独立IO共11份Passed收据组成最终证明；超时原大批回执完全排除。切换版映射阶段资源APM70/240、LUT14993/66600、FF18587/133200、DRM16.5/155、IO130/300；映射资源FF数与网表展开FF数18596口径不同，不混写。资源空余不等于已测得更高帧率。

最终CDC proof已封存，19089321字节，SHA256 `650f0d84d5929b410f91c9fbcca7d630d418c3749f938681bdac57fad844fdc2`。bit authority-b 曾在proof文件尚写入时绑定了中间SHA，被严格输入校验拒绝，未生成authority或位流；失败request/driver保留。后改新driver-c，先核对已完成shard driver最终成功记录和完整proof SHA/JSON，再重新绑定与全量复核；原生产器、native结果和proof原件均未改动。

## 实屏切换验收与推送授权

用户反馈“切换没问题，可以推送”。该反馈仅确认原图／矫正实屏切换，未将横纹成因、LED状态或全视场光学校准写为通过。确认记录追加在证据包 `user-acceptance.json`，同名汇总以SHA256绑定；原206项native/仿真/UART封存字节及manifest保持不变。当前按用户授权提交并推送 `codex/camera720-view-toggle`。
