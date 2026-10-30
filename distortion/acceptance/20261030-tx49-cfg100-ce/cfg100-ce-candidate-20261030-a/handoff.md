# CFG100-1030-CE-CANDIDATE-ONE

已完成这个独立最小候选；功能定向与诊断setup目标通过，整体时序/硬件仍未放行。

只替换自研 `ddr_video_output_1080_board` 的bad_id组合表达式，保留32位模减法、同拍fault优先及全部寄存器/握手/reset。111角色/33个实际设计入口，其余110角色原样；未修改vendor、FDC、时钟、8ns约束、例外、seed或发布入口。候选SHA256 `decb0ad22222ce8c47ae8beefbb8afd2c85b5a4418bd24b8815fc913a03aa253`。

## 实际结果

- CPU独立模序/旧新表达式：295250例，0差异，0.340秒；不是形式等价或XZ证明。
- RTL v2：28场景、5同拍碰撞、1合法grant+abort、157283拍新旧公开输出逐拍一致，24 good、7 bad、21 fault，14.385秒。身份/半范围/回绕/同bank与CRC/边界/最终像素/abort/背压/reset已覆盖。
- 原directed-a在最终数量门禁错误期望25处失败，实际24；只修bench常数后在新run通过，原失败保留。FIFO跨reset总请求1319/返回1318，未单独测量取消计数；不把相差1冒充精确取消证明。
- 综合CE锥：两个目标深度15→14、相关单元23→21；未将依赖转到D/R或把CE常量化。资源报告首份UNKNOWN来自解析器跨RAM同步写边界，依据本机官方RAM模型补审后可比，原报告保留；资源gate未重跑。
- 同会话compile/synthesize/dev_map：native0/host0，325.935秒；map LUT16356 / FF17627 / APM69 / DRM17.5，真实DDR/PLL无未知黑盒，32KiB缓存与异步FIFO的DRM、动态correction与配置链保留。
- 唯一PNR：native0/host0，290.570秒；当前map PCF145/145消费，DDR门控两项及CPD固定项落地，Place-0006未出现。route LUT16199 / FF17627 / APM69 / DRM17.5。
- 独立最终DB双角STA：native0/host0，36.101秒。slow setup最差+.193ns（0失败）、fast +2.737ns；slow/fast hold +.136/+.101ns，removal +.355/+.247ns，MPW +.035/+.035ns，观测项均0失败。
- 原跨域setup组最差-0.004ns→0.579ns（当前665检查端点、0失败）；125MHz同域最差+.172→+.193ns。没有额外重查两个原路径的单独正slack，不能把组最差当其精确值。+.193ns仍是较薄裕量。
- slow/fast recovery每角7组245检查仍失败，最差-6.280/-3.946ns；不跨角相加成独立FF。board27→rst_clk仍Timed(unsafe)，interaction WNS -4.255ns是相关视图，不能另加到245。

## 最终绑定与边界

最终保存ADF：`physical-a/final/board1080_top-final-routed.adf`，SHA256 `8c47cd66346d6a94cc10cd250ea8b568054128985a208b8f00e32fc4ad2a74bd`，16061700字节。当前map SHA `3f25e4384b5a5f0075fe41e61344964a6c9d51ded1ccfd7ac6a2844bd6da2c83`，PCF SHA `b4213ff77ee12cbab3cb9ab6a8202c39d18a3f63ac9ccb2f887d1004d86cb3f4`；FDC保持 `2ff6dd8510e7b0566f550143561ac4138c19cd255944811b4561979f6e8b0f23`。精确工具argv/cwd/PID/退出在delivery-receipt与每阶段admission/result；复用runner的旧Marker字面值保留，当前实验身份以本handoff、输入hash与路径为准。

11时钟、121时钟对；6域有同域setup/hold数据，另5域缺项为UNKNOWN。no_input_delay54、no_output_delay110（含DDR pad）、unexpandable2；实际HDMI AC/BASE V1.4 skew、DDR动态训练、FIFO宏内/Gray skew与MTBF、实物over_temp仍未签核。8ns/min0是既有诊断约束，不是CDC安全证明。

8个原生例外表已按XML完整提取，逐角max-delay setup128/recovery73、multicycle setup40/hold40条报告行，不是独立端点数量。请求report_max_skew但原生无skew表，保持UNKNOWN。旧collector将XML误认ID而漏摘要的v1原记录保留，`physical-a/diagnostic-summary-v2.json`修正摘要；不重跑STA或审计器。

本次没有新全帧/长期/HDMI/实板测试，不继承旧native8对新源码的功能覆盖。没有bit、硬件计划、设备访问、Git写入或电源设置变更。497个本轮冻结输入及原候选7b89 ADF复核无漂移；旧B/+.191/.144与历史失败保留。全部正式/硬件门禁仍false。

## 恢复点与下一动作

本次三个重型阶段均自然终态、所属原生进程退出，无需恢复或重跑。先读`delivery-receipt.json`和`physical-a/diagnostic-summary-v2.json`即可复核。保留该CE诊断候选；真正物理放行仍需厂商确认245 recovery的动态训练/首有效边沿契约，以及独立IO/温度准入。不要用删检查或继续同配置PNR代替解决。后续若推进动态角度/Gamma等完整板级功能，应另立候选并做相应功能/时序绑定，不能借本固定Brown/0°/Gamma关闭结果放行。
