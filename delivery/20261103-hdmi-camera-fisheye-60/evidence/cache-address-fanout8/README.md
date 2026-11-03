# Cache 最终地址网络 fanout8 原生探针

状态：综合复制与局部函数等价检查通过；完整 I 候选的布局布线收益待实际 native 报告判定。

探针使用真实 `ddr_neighbour_cache_scatter4_rowpipe`，WIDTH=1920、HEIGHT=1080、INDEX_BITS=10、ROW_PADDED_INDEX=1、REGISTERED_RETURN=1。源功能版本 SHA 为 `5c82ee0065ed6a9b01e5a9d63953478daa80b79b9b9cdcfe8a0c226de37f2107`。候选只在 `even_a/odd_a/even_b/odd_b` 四条最终地址 wire 前添加 `(* syn_maxfan=8 *)`，剥离属性和换行归一化后全文相同。

两版均使用 PDS 2025.2 build 211867、PG2L100H-6FBG676，完成 compile、synthesize、device-map。接口用 32 位配置口写入输入寄存器，并通过动态结果选择器观察全部结果；缓存的每个 DDR 数据位和结果都保持可控、可观察。首次直接引出所有端口需要 645 个 IO，超过器件 300 个 IO，因而调整了探针接口；缓存源码及被审计的内部地址结构保持。

`verification.json` 核验 56 个地址位：原来每位 32 个 DRM 地址负载，增加属性后变为四组，每组 8 个，共 224 路地址驱动输出。原 1792 条 DRM 地址连接精确分组，未丢失或增加。每一复制 LUT 的投影 INIT 真值表，在同名输入上与基线完全一致；验证包含基线共享 LUT6D 的 Z 与 Z5 输出拆分和无关输入消除。源码及综合网表 SHA 均被记录。

映射后资源：LUT 5537→5651，增加 114；FF 3135、DRM 69、APM 2 均不变。上述 fanout=8 数值来自完整实际综合网表逐负载计数；device-map 成功及资源增量独立保留。此探针没有运行布局布线，最终 mapped/routed 网的复制保留、负载分配和延迟须在完整候选复核。

目录内保留两版源、相同 top、时钟约束、原生构建 Tcl、过滤 license 路径后的日志、映射资源报告和压缩综合网表。`verify.py` 使用探针工作目录 `D:/f60-work/cache-addr-probe`；在其他机器重建时将两个 build.tcl 中该前缀与验证脚本的 root 改为新的短路径即可。属性修复与 REGISTERED_RETURN 的协议功能测试分开记录。
