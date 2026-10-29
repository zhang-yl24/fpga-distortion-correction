# 1080P 地址流水整合候选

本地分支 `codex/board1080-rowpipe` 合并本机仿真入口与 DDR 审计两个开发分支，直接基于队友已推送源码推进。缺少队友旧构建报告不影响使用源码；新的功能和时序结果由本机重新生成，旧报告只作定位参考。

本轮将已有 rowpipe 接入 CDC-reset 整链，保留原入口可回退。新 sampler 与旧 sampler 使用相同模块名，必须互斥编译。独立入口为：

- `distortion/board/board1080_rowpipe_top.v`
- `distortion/board/board1080-rowpipe-sources.json`，109 项源/头/约束/IP 清单，只有 cache、sampler、顶层三项替换，FDC/RCF 与复位逻辑未变。
- `distortion/tools/run_board1080_rowpipe_system_sim.py`，以 `build/board1080-rowpipe-reproduction` 为工作目录；原整链的 CRC、反压、故障隔离、公共复位及 same-source small/native 检查均保留。

rowpipe 将 y×WIDTH 乘积注册，再相加 x/邻域偏移，针对原地址乘加路径。1920×1080 时仍用 INDEX_BITS=7，sampler/cache 的 TAG_W=25（含几何遮罩），没有改变缓存容量或 DDR 协议。是否改善实际余量必须由新布局布线验证。

本轮实际验证：11 项 CPU 闭包/来源拒绝/配置恢复测试通过；Vivado 2017.4 编译、展开、仿真均退出 0，新的 32×16 八帧整链通过，4096 像素与独立 CPU golden 一致，最终排空、故障隔离及公共复位恢复通过。原始记录在 `distortion/build/board1080-rowpipe-reproduction/local-small-20261028-a/board1080-system-simulation.json`，哈希摘要见 `distortion/results/board1080-rowpipe-small-20261028.json`。

新候选随后完成自己的原生1920×1080八帧回归：16588800像素/CRC一致、稳态30.000fps、无丢帧/输出下溢/CRC错误，银行复用和最终排空通过。最坏3816061个125MHz周期，37项源/33输入及衍生文件前后无漂移，compile/elaborate/simulate均0。结果见 `distortion/results/board1080-rowpipe-native-20261028.json`。逐帧处理周期与旧版相同，rowpipe没有直接提升吞吐；小尺寸测试承担故障/复位注入，native有意只跑正常八帧流，不能混淆这两种覆盖。

本机最终STA也已生成：主域slow setup +0.447ns，但hold每角仍1项−0.037/−0.222ns、recovery slow245/fast234。随后完整200ps时钟树hold定向试验退出0、无原生错误，十表与原试验完全相同，无收益；见 `handoff/BOARD1080_HOLDFIX_20261028.md`。没有生成位流或操作开发板，DDR/IO/CDC与真实光学输入仍未签核。不同PDS版本不能把旧+.116与新+.447当作单变量因果提升。

下一步按 `handoff/DDR_IP_CONSTRAINT_PLAN.md` 在独立候选中集成适用的IP内部具体reset例外，保留自研CDC与真实数据setup/hold；入口1项另处理。DDR首个PLL的原始复位不可直接与该PLL的LOCK相与后反馈给整个IP，以免启动死锁。官方IP约束可作设计依据，但不能照搬全局board27异步组隐藏边界。当前30fps保底与60fps改造预算见 `handoff/BOARD1080_PERFORMANCE_BUDGET.md`。
