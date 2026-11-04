# INDEX8 慢查询缩短实验 c

这是一份独立实验设计，尚不具有物理或板测放行资格。已发布的 `45223998ce3695960297937519d37759499bb4f5`、原缓存源码和 SRAM 位流均保持不变。

原缓存源码 SHA256 为 `d4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e`。实验 c 为 `2828700483c478688cddf249608456f4f1253c5091687c11accc98a833b2df6e`。实验保持 INDEX8、128 像素块、每块八个 DDR beat、单 outstanding、两组 even/odd 双端口像素 RAM、现有 RGB565 展开与所有权契约。

## 改动与原因

慢查询原来重新计算四个邻点的线性地址，并逐个经过 SELECT、CHECK、LOAD、PICK。快查询前端已经计算过完整四邻点地址，因此实验在接收慢查询时保存四个像素编号和 bounds，直接装入第一个 selected 地址；PICK 后直接装入下一个地址。它移除了慢路径的重复乘加与 SELECT 等待。

CHECK 同拍对已注册的 selected 地址进行同步 RAM 读。只有 tag 命中时，下一拍的 PICK 才消费这个字；miss 的这次读值被丢弃，继续原 AR/FILL/末 commit/LOAD/PICK 路径。RAM 读使能由 CHECK 状态决定，不由 tag 比较结果组合控制。越界邻点写零，不计 hit，不消费读出的 RAM 值。

完整块最后一个 beat 真正写入 RAM 并发布 tag/valid 后，如果仍有未处理邻点，实验进入 BULK_CHECK。全部有效邻点的完整 tag 都 resident 时，用原四个 RAM 读端口一次读齐，再进入原 RESULT。若有同 index 不同 tag 或其他未命中，回退逐邻点路径，保留已保存的早邻点。最后一个邻点自身 miss 时没有批读收益，直接进入原 LOAD，避免额外检查周期。

完整查询快照独立于前端 younger query；同拍接收慢查询和移动下一查询时，非阻塞赋值读取旧 pixel_number/bounds。批读仅补计当前 miss 邻点之后的有效 hit，保持公开 hit/miss/query 计数含义。

## 已完成的验证

- 独立缓存单元测试：639 宽、INDEX3，以及 1920×1080 的 INDEX7/8/9 均通过；包括独立像素与 CRC、warm II、输入/输出背压、frame drain、AR 同拍首 R、R 间隙、故障与复位。
- 实验 c 单元实际执行 16.104 秒，699 fills、1,544 个输出由原独立像素 oracle 检查。
- 独立末 commit 碰撞测试：第九个 R、错误 final RID、缺失 RLAST、末 commit 前 reset 四类边界，864 个 RAM 像素检查通过。
- 普通和持续输入小系统通过；原 bench、CPU 像素/掩码/CRC、KEY 模式切换、ownership 和最终 drain 断言逐字保留。
- 完整 2,073,600 查询地址轨迹模型复现原 37,483 fills、34,705 slow queries、2,038,895 fast queries，四版本最终 tag 状态和访问计数一致。按实际 n3 跳过 BULK_CHECK 的 c 状态规则，局部状态差分为 288,045 周期，即 2.30436ms@125MHz。

以上地址与状态模型不重新计算共享 DDR 仲裁、mapper/writer 背压、显示相位或物理布线。2.30436ms 不能直接从板测处理时间相减后宣称达到 30 FPS。

## 本次完整系统实验

`run_combined_system_probe_c.py` 使用已验 INDEX8 的实际 22 份 prepared 源，仅替换缓存一项；其余 21 项（含原 bench）、三份 header 和 17 个 fixture 逐字复制。普通和持续输入分别先执行同源小门禁，再运行完整 1080p。新报告明确是实验，不调用原 provider 的 release 验证或访问开发板。

当前 native runner 检查了对应 small gate，但其原始 native 报告没有将 small 报告纳入 watched 输入。这一证明链缺口保留原样，由独立保存结果复核额外绑定 small、unit、源、fixture 与完整输出，不改运行中的 runner，也不倒写原报告。

## 必须另外检查的物理风险

新增 slow 快照和四路 tag/valid 查询会增加寄存器、mux 和局部扇出。CHECK 增加 RAM 读状态，批读增加 RAM 地址选择。原 INDEX8 的时序、RAM primitive 映射、CDC 和约束放行均不能继承。研究性的 raw 布局布线只能筛选 core 时序与实际 RAM 结构；只有新版本完成其全部物理、位流与实板门禁后才能上板和声明新帧率。
