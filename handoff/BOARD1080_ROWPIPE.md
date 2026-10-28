# 1080P 地址流水整合候选

本地分支 `codex/board1080-rowpipe` 合并本机仿真入口与 DDR 审计两个开发分支，直接基于队友已推送源码推进。缺少队友旧构建报告不影响使用源码；新的功能和时序结果由本机重新生成，旧报告只作定位参考。

本轮将已有 rowpipe 接入 CDC-reset 整链，保留原入口可回退。新 sampler 与旧 sampler 使用相同模块名，必须互斥编译。独立入口为：

- `distortion/board/board1080_rowpipe_top.v`
- `distortion/board/board1080-rowpipe-sources.json`，109 项源/头/约束/IP 清单，只有 cache、sampler、顶层三项替换，FDC/RCF 与复位逻辑未变。
- `distortion/tools/run_board1080_rowpipe_system_sim.py`，以 `build/board1080-rowpipe-reproduction` 为工作目录；原整链的 CRC、反压、故障隔离、公共复位及 same-source small/native 检查均保留。

rowpipe 将 y×WIDTH 乘积注册，再相加 x/邻域偏移，针对原地址乘加路径。1920×1080 时仍用 INDEX_BITS=7，sampler/cache 的 TAG_W=25（含几何遮罩），没有改变缓存容量或 DDR 协议。是否改善实际余量必须由新布局布线验证。

本轮实际验证：11 项 CPU 闭包/来源拒绝/配置恢复测试通过；Vivado 2017.4 编译、展开、仿真均退出 0，新的 32×16 八帧整链通过，4096 像素与独立 CPU golden 一致，最终排空、故障隔离及公共复位恢复通过。原始记录在 `distortion/build/board1080-rowpipe-reproduction/local-small-20261028-a/board1080-system-simulation.json`，哈希摘要见 `distortion/results/board1080-rowpipe-small-20261028.json`。

该结果仅证明小尺寸整链；未新跑本候选的 native 八帧或最终 STA，不借用旧版本 1080P 回归宣称新版本通过。也没有生成位流或操作开发板。DDR 内部 recovery、外部 IO 和真实光学输入仍须分别解决。

下一步使用此候选生成本机最终 STA，获取自己的逐端点失败清单并评估地址路径余量；同源小尺寸结果也可用于后续 native 八帧入口。DDR 首个 PLL 的原始复位不可直接与该 PLL 的 LOCK 相与后再反馈给整个 IP，以免启动死锁。内部训练复位的处理须分别核实 gate/首有效边沿关系。
